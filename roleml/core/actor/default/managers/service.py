import logging
import pickle
from typing import Any, Callable, Union

from fasteners import ReaderWriterLock

from roleml.core.actor.default.managers.channels import ChannelCallManagerMixin
from roleml.core.actor.helpers import PayloadsPickledMessage
from roleml.core.actor.manager import BaseServiceManager
from roleml.core.context import RoleInstanceID
from roleml.core.messaging.exceptions import InvocationAbortError, InvocationRefusedError
from roleml.core.messaging.types import Args, Payloads, Tags
from roleml.core.role.base import Role
from roleml.core.role.exceptions import CallerError, ChannelNotFoundError, HandlerError
from roleml.core.role.types import Message
from roleml.core.status import Status


SERVICE_UNIFIED_MESSAGING_CHANNEL = 'SERVICE'


class ServiceManager(BaseServiceManager, ChannelCallManagerMixin):

    channels: dict[str, dict[str, Callable[[RoleInstanceID, Args, Payloads], Any]]]
    channel_lock: ReaderWriterLock
    """ Locks outer dict of `channels` """

    def initialize(self):
        self.channels = {}
        self.channel_lock = ReaderWriterLock()
        self.logger = logging.getLogger('roleml.managers.service')
        self.procedure_provider.add_procedure(SERVICE_UNIFIED_MESSAGING_CHANNEL, self._on_receive_service_message)
        self.role_status_manager.add_callback(Status.FINALIZING, self._on_role_status_finalizing)

    def add_role(self, role: Role):
        with self.channel_lock.write_lock():
            services = self.channels[role.name] = {}
        for channel_name, attribute_name in role.services.items():
            handler = getattr(role, attribute_name)
            services[channel_name] = handler

    def _on_role_status_finalizing(self, instance_name: str, _):
        with self.channel_lock.write_lock():
            del self.channels[instance_name]

    def _on_receive_service_message(self, sender: str, tags: Tags, args: Args, payloads: Payloads):
        try:
            from_instance_name: str = tags['from_instance_name']
            to_instance_name: str = tags['to_instance_name']
            to_channel_name: str = tags['to_channel_name']
        except KeyError:
            raise AssertionError('unspecified from/to instance or channel name')

        try:
            return self._handle_service_call(
                sender, from_instance_name, to_instance_name, to_channel_name, args, payloads)
        except CallerError as e:
            raise InvocationAbortError(str(e))
        except ChannelNotFoundError as e:
            raise InvocationRefusedError(str(e))
        # other exceptions will just raise and converted into procedure provider error

    def call(self, instance_name: str, target: RoleInstanceID, channel_name: str,
             message: Union[Message, PayloadsPickledMessage]) -> Any:
        self.logger.debug(f'calling service on {target}/{channel_name} from {instance_name}, args = {message.args}')
        if target.actor_name == self.context.profile.name:
            return self._call_local(instance_name, target.instance_name, channel_name, message)
        else:
            return self._call_remote(instance_name, target, channel_name, message)

    def _call_local(self, from_instance_name: str, to_instance_name, to_channel_name: str,
                    message: Union[Message, PayloadsPickledMessage]) -> Any:
        try:
            from_actor_name = self.context.profile.name
            return self._handle_service_call(
                from_actor_name, from_instance_name, to_instance_name, to_channel_name, message.args,
                pickle.loads(message.payloads) if isinstance(message, PayloadsPickledMessage) else message.payloads)
        except CallerError:     # AssertionError converted in _handle_service_call
            self.logger.error(f'failed to call service {to_instance_name}/{to_channel_name} (caller error)')
            raise
        except ChannelNotFoundError:
            self.logger.error(f'cannot find service channel {to_instance_name}/{to_channel_name}')
            raise
        except Exception as e:
            self.logger.error(f'failed to call service {to_instance_name}/{to_channel_name} (handler error)')
            raise HandlerError(str(e)) from e

    def _call_remote(self, instance_name: str, target: RoleInstanceID, channel_name: str,
                     message: Union[Message, PayloadsPickledMessage]) -> Any:
        tags = {
            'from_instance_name': instance_name,
            'to_instance_name': target.instance_name,
            'to_channel_name': channel_name
        }
        try:
            return self.procedure_invoker.invoke_procedure(
                self.context.contacts.get_actor_profile(target.actor_name),
                SERVICE_UNIFIED_MESSAGING_CHANNEL, tags, message.args, message.payloads
            )
        except InvocationRefusedError as e:
            self.logger.error(f'cannot find service channel {target}/{channel_name}')
            raise ChannelNotFoundError(str(e)) from None
        except InvocationAbortError as e:
            self.logger.error(f'failed to call service {target}/{channel_name} (caller error): {e}')
            raise CallerError(str(e)) from None
        except Exception as e:
            self.logger.error(f'failed to call service {target}/{channel_name} (handler error): {e}')
            raise HandlerError(str(e)) from None

    def _handle_service_call(
            self, from_actor_name: str, from_instance_name: str, to_instance_name: str, to_channel_name: str,
            args: Args, payloads: Payloads) -> Any:
        with self._execute_environment_for_role(to_instance_name, None):
            try:
                with self.channel_lock.read_lock():
                    handler = self.channels[to_instance_name][to_channel_name]
            except KeyError:
                description = self._describe_handler(
                    from_actor_name, from_instance_name, to_instance_name, to_channel_name)
                self.logger.info(f'attempting to call non-existent {description}')
                raise ChannelNotFoundError(f'{description}')
            else:
                try:
                    return self._handle_call_impl(
                        from_actor_name, from_instance_name, to_instance_name, to_channel_name, handler, args, payloads)
                except AssertionError as e:
                    raise CallerError(str(e)) from e

    def _describe_handler(
            self, from_actor_name: str, from_instance_name: str, to_instance_name: str, channel_name: str) -> str:
        return f'service channel {to_instance_name}/{channel_name}'
