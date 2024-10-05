import logging
import pickle
from io import BytesIO
from typing import Optional

from flask import Flask, request, jsonify, send_file
from werkzeug.exceptions import BadRequest
from werkzeug.serving import make_server

from roleml.core.context import ActorProfile, Contacts, ActorNotFoundError
from roleml.core.messaging.base import ProcedureProvider
from roleml.core.messaging.exceptions import InvocationAbortError, InvocationRedirectError, InvocationRefusedError
from roleml.core.messaging.types import Args, MessageHandler
from roleml.extensions.messaging.util import TagReader, is_namedtuple
from roleml.shared.types import LOG_LEVEL_INTERNAL
from roleml.shared.util import load_bytes, resolve_host_port

__all__ = ['FlaskProcedureProvider']


def _check_source_ip(expected_ip: str) -> bool:
    if not request.remote_addr:
        return False
    remote_ip = resolve_host_port(request.remote_addr)[0]
    if remote_ip != expected_ip:
        return False
    return True


class FlaskProcedureProvider(ProcedureProvider):

    def __init__(self, local_name: str, local_address: str, contacts: Contacts,
                 *, host: Optional[str] = '0.0.0.0', check_source_ip: bool = False,
                 enable_handshake: bool = True, remove_contact_on_handwave: bool = True):
        super().__init__(local_name, local_address, contacts)
        self.host = host or resolve_host_port(self.local_address)[0]
        self.port = resolve_host_port(self.local_address)[1]
        self.check_source_ip = check_source_ip

        self._flask = Flask('RoleML')
        try:
            self._server = make_server(self.host, self.port, self._flask, threaded=True)
            self._context = self._flask.app_context()
            self._context.push()
        except Exception:   # noqa: using Logger.exception()
            self.logger.exception('failed to start procedure provider')
            raise

        self._handlers: dict[str, MessageHandler] = {}

        self.supports_handshake_handwave = enable_handshake
        if enable_handshake:
            self._setup_handshake()
            self._setup_handwave()
        self.remove_contact_on_handwave = remove_contact_on_handwave
    
    def _setup_handshake(self):
        def handshake_view_func():
            if not request.is_json:
                return 'invalid handshake message', 401
            assert request.json is not None
            args: Args = request.json
            actor_name, address = args['name'], args['address']
            if self.check_source_ip and not _check_source_ip(resolve_host_port(address)[0]):
                return 'invalid handshake message sender', 401
            self.contacts.add_contact(ActorProfile(actor_name, address))
            self.logger.info(f'received handshake with actor {actor_name}')
            return jsonify(None)
        self._flask.add_url_rule(f'/__HANDSHAKE', view_func=handshake_view_func, methods=('GET', 'POST'))

    def _setup_handwave(self):
        def handwave_view_func():
            if not request.is_json:
                return 'invalid handwave message', 401
            assert request.json is not None
            args: Args = request.json
            actor_name = args['name']
            profile = self.contacts.get_actor_profile(actor_name)
            if self.check_source_ip and not _check_source_ip(resolve_host_port(profile.address)[0]):
                return 'invalid handwave message sender', 401
            if self.remove_contact_on_handwave:
                self.contacts.remove_contact(actor_name)
            self.logger.info(f'received handwave with actor {actor_name}')
            return jsonify(None)
        self._flask.add_url_rule(f'/__HANDWAVE', view_func=handwave_view_func, methods=('GET', 'POST'))

    def add_procedure(self, name: str, handler: MessageHandler):
        def view_func():
            try:
                active_handler = self._handlers[name]
                source_name = request.headers['from']

                if request.method == 'GET':
                    # not used by the requests invoker anymore
                    args: Args = dict(request.json) if request.is_json else {}  # type: ignore
                    payloads = {}
                else:
                    # deserialize files
                    files = request.files.to_dict()
                    args: Args = load_bytes(files.pop('_args_').stream.read()) if '_args_' in files else {}
                    if 'payloads-pre-pickled' in request.headers:
                        payloads = pickle.loads(files['_payloads_'].stream.read()) if '_payloads_' in files else {}
                    else:
                        payloads = {filename: load_bytes(files[filename].stream.read()) for filename in files}

                try:
                    source_profile = self.contacts.get_actor_profile(source_name)
                    if self.check_source_ip and not _check_source_ip(resolve_host_port(source_profile.address)[0]):
                        return 'invalid handshake message sender', 401
                except ActorNotFoundError:
                    return 'invalid message sender', 401
                self.logger.log(LOG_LEVEL_INTERNAL, f'received message to channel ({name}) from ({source_name})')

                result = active_handler(source_name, TagReader(request.headers), args, payloads)

                if is_namedtuple(result):
                    # cannot JSON serialize a namedtuple otherwise type information will be lost
                    return send_file(BytesIO(pickle.dumps(result)))

                try:
                    return jsonify(result)  # including None (null)
                except TypeError:
                    # https://developer.mozilla.org/zh-CN/docs/Web/HTTP/Basics_of_HTTP/MIME_types
                    file = BytesIO(result) if type(result) is bytes else BytesIO(pickle.dumps(result))
                    return send_file(file, mimetype='application/octet-stream')

            except BadRequest:
                return 'Invalid message format', 400
            
            except InvocationRefusedError as e:
                self.logger.log(LOG_LEVEL_INTERNAL, f'handler of channel ({name}) refused to handle message: {e}')
                return str(e), 412

            except (InvocationAbortError, AssertionError) as e:
                self.logger.log(
                    LOG_LEVEL_INTERNAL, f'message sender error when processing message in channel ({name}): {e}')
                return str(e), 400

            except InvocationRedirectError as e:
                self.logger.log(LOG_LEVEL_INTERNAL, f'handler of channel ({name}) redirected message to {e}')
                return str(e), 410

            except Exception as e:
                self.logger.log(LOG_LEVEL_INTERNAL, f'unhandled error when processing message in channel ({name})')
                return str(e), 500

        view_func.__name__ = f'on_route_{name}'
        self._flask.add_url_rule(f'/{name}', view_func=view_func, methods=('GET', 'POST'))
        self._handlers[name] = handler

    def run(self):
        logger = logging.getLogger('werkzeug')
        logger.setLevel('WARN')
        self._server.serve_forever()

    def stop(self):
        self._server.shutdown()
