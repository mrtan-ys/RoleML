import logging
import pickle
import concurrent.futures
from collections.abc import Mapping
from typing import Any, Optional, Union

try:
    import grpc
except ImportError as exc:
    exc.msg = 'gRPC dependency missing. Please install grpcio in your environment to enable gRPC messaging.'
    raise

from .messaging_pb2 import Handshake, Handwave, Request, Response
from .messaging_pb2_grpc import RoleMLMessagingServicer, RoleMLMessagingStub, add_RoleMLMessagingServicer_to_server

from roleml.core.context import ActorNotFoundError, ActorProfile, Contacts
from roleml.core.messaging.base import MessagingComponent
from roleml.core.messaging.exceptions import \
    HandshakeError, HandwaveError, InvocationRedirectError, ProcedureNotFoundError, \
    InvocationAbortError, InvocationRefusedError, InvalidInvokerError, InvocationFailedError
from roleml.core.messaging.types import Args, MessageHandler, Payloads, Tags
from roleml.shared.types import LOG_LEVEL_INTERNAL
from roleml.shared.util import resolve_host_port


MAX_MESSAGE_LENGTH = 1024 * 1024 * 1024


class GRPCMessagingServicerImpl(RoleMLMessagingServicer):

    def __init__(self, contacts: Contacts, logger: logging.Logger, *, remove_contact_on_handwave: bool):
        self.contacts = contacts
        self.logger = logger

        self.remove_contact_on_handwave = remove_contact_on_handwave

        self._handlers: dict[str, MessageHandler] = {}

    def add_procedure(self, name: str, handler: MessageHandler):
        self._handlers[name] = handler

    def invoke_procedure(self, request: Request, context: grpc.ServicerContext) -> Response:
        try:
            self.contacts.get_actor_profile(request.source)
        except ActorNotFoundError:
            context.abort(grpc.StatusCode.UNAUTHENTICATED, 'actor not identified')
            assert False

        procedure = request.procedure
        try:
            handler = self._handlers[procedure]
        except KeyError:
            context.abort(grpc.StatusCode.UNIMPLEMENTED, 'procedure not found')
            assert False

        try:
            tags = pickle.loads(request.tags) or {}
            args = pickle.loads(request.args) or {}
            payloads = pickle.loads(request.payloads) or {}
        except ModuleNotFoundError as e:
            self.logger.exception(f'missing module {e.name} for deserialization')
            context.abort(grpc.StatusCode.INTERNAL, f'missing module {e.name} for deserialization')
            assert False
        except Exception:   # noqa
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, 'corrupted data')
            assert False

        try:
            result = handler(request.source, tags, args, payloads)
        except InvocationRefusedError as e:
            self.logger.log(
                LOG_LEVEL_INTERNAL, f'handler of channel ({procedure}) refused to handle message: {e}')
            context.abort(grpc.StatusCode.NOT_FOUND, str(e))
            assert False
        except (InvocationAbortError, AssertionError) as e:
            self.logger.log(
                LOG_LEVEL_INTERNAL, f'message sender error when processing message in channel ({procedure}): {e}')
            context.abort(grpc.StatusCode.FAILED_PRECONDITION, str(e))
            assert False
        except InvocationRedirectError as e:
            self.logger.log(
                LOG_LEVEL_INTERNAL, f'handler of channel ({procedure}) redirected message to {e}')
            context.set_trailing_metadata((("redirect", str(e)),))
            context.abort(grpc.StatusCode.UNAVAILABLE, str(e))
            assert False
        except Exception as e:
            self.logger.log(
                LOG_LEVEL_INTERNAL, f'unhandled error when processing message in channel ({procedure}): {e}')
            context.abort(grpc.StatusCode.UNKNOWN, f'unhandled error: {e}')
            assert False
        else:
            return Response(content=pickle.dumps(result))

    def handshake(self, request: Handshake, context: grpc.ServicerContext) -> Response:
        actor_name, address = request.name, request.address
        self.contacts.add_contact(ActorProfile(actor_name, address))
        self.logger.info(f'received handshake with actor {actor_name}')
        return Response(content=None)

    def handwave(self, request: Handwave, context: grpc.ServicerContext) -> Response:
        actor_name = request.name
        if self.remove_contact_on_handwave:
            self.contacts.remove_contact(actor_name)
        self.logger.info(f'received handwave with actor {actor_name}')
        return Response(None)


class GRPCMessagingComponent(MessagingComponent):

    supports_handshake_handwave = True
    
    def __init__(self, local_name: str, local_address: str, contacts: Contacts,
                 *, remove_contact_on_handwave: bool = True):
        super().__init__(local_name, local_address, contacts)
        self.server = grpc.server(
            concurrent.futures.ThreadPoolExecutor(), 
            options=(
                ('grpc.max_send_message_length', MAX_MESSAGE_LENGTH),
                ('grpc.max_receive_message_length', MAX_MESSAGE_LENGTH)
            )
        )
        self.server.add_insecure_port(f'[::]:{resolve_host_port(local_address)[1]}')
        self.servicer = GRPCMessagingServicerImpl(
            self.contacts, self.logger, remove_contact_on_handwave=remove_contact_on_handwave)
        add_RoleMLMessagingServicer_to_server(self.servicer, self.server)
        self.logger.info('using gRPC messaging component')
    
    def add_procedure(self, name: str, handler: MessageHandler):
        self.servicer.add_procedure(name, handler)
    
    def invoke_procedure(
            self, target: Union[str, ActorProfile], name: str,
            tags: Optional[Tags] = None, args: Optional[Args] = None, payloads: Optional[Union[Payloads, bytes]] = None
            ) -> Any:
        if isinstance(target, str):
            target = self.contacts.get_actor_profile(target)
        with grpc.insecure_channel(
            target.address,
            options=[
                ('grpc.max_send_message_length', MAX_MESSAGE_LENGTH),
                ('grpc.max_receive_message_length', MAX_MESSAGE_LENGTH)
            ]) as channel:
            stub = RoleMLMessagingStub(channel)
            try:
                if payloads is None:
                    payloads = {}
                response: Response = stub.invoke_procedure(
                    Request(
                        source=self.local_name, procedure=name,
                        tags=pickle.dumps(tags), args=pickle.dumps(args),
                        payloads=pickle.dumps(payloads) if isinstance(payloads, Mapping) else payloads
                        # https://github.com/python/typing/issues/552
                        # payloads=payloads if isinstance(payloads, (bytes, bytearray, memoryview)) else pickle.dumps(payloads)
                    )
                )
            except grpc.RpcError as e:
                assert isinstance(e, grpc.Call)
                status: grpc.StatusCode = e.code()
                if status == grpc.StatusCode.UNIMPLEMENTED:
                    raise ProcedureNotFoundError(e.details())
                elif status == grpc.StatusCode.NOT_FOUND:
                    raise InvocationRefusedError(e.details())
                elif status == grpc.StatusCode.UNAUTHENTICATED:
                    raise InvalidInvokerError(f'current actor not identified by {target}')
                elif status == grpc.StatusCode.FAILED_PRECONDITION:
                    raise InvocationAbortError(e.details())
                elif status == grpc.StatusCode.UNAVAILABLE:
                    metadata = e.trailing_metadata()
                    if metadata:
                        redirect_name = next((value for key, value in metadata if key == 'redirect'), None)
                        if redirect_name is not None:
                            return self.invoke_procedure(redirect_name, name, tags, args, payloads)
                    raise InvocationFailedError(e.details())
                else:
                    raise InvocationFailedError(e.details())
            else:
                return pickle.loads(response.content)
    
    def handshake(self, target: Union[str, ActorProfile]):
        if isinstance(target, str):
            target = self.contacts.get_actor_profile(target)
        try:
            with grpc.insecure_channel(target.address) as channel:
                stub = RoleMLMessagingStub(channel)
                stub.handshake(Handshake(name=self.local_name, address=self.local_address))
        except Exception as e:
            raise HandshakeError(target) from e
        self.logger.info(f'handshake with {target.name} success')
    
    def handwave(self, target: Union[str, ActorProfile]):
        if isinstance(target, str):
            target = self.contacts.get_actor_profile(target)
        try:
            with grpc.insecure_channel(target.address) as channel:
                stub = RoleMLMessagingStub(channel)
                stub.handwave(Handwave(name=self.local_name))
        except Exception as e:
            raise HandwaveError(target) from e
        self.logger.info(f'handwave with {target.name} success')

    def run(self):
        self.server.start()
    
    def stop(self):
        self.server.stop(None)
