import json
import pickle
from io import IOBase, BytesIO
from typing import Any, Optional, Union

import requests

from roleml.core.context import ActorProfile
from roleml.core.messaging.base import ProcedureInvoker
from roleml.core.messaging.exceptions import (
    HandshakeError, HandwaveError, InvocationAbortError, InvocationRefusedError, ProcedureInvokerError,
    MsgConnectionError, InvalidInvokerError, ProcedureNotFoundError, InvocationFailedError)
from roleml.core.messaging.types import Args, Payloads, Tags, MyArgs, MyPayloads
from roleml.extensions.messaging.util import insert_tags
from roleml.shared.util import load_bytes

__all__ = ['RequestsProcedureInvoker']


class RequestsProcedureInvoker(ProcedureInvoker):

    def invoke_procedure(
            self, target: Union[str, ActorProfile], name: str,
            tags: Optional[Tags] = None, args: Optional[Args] = None, payloads: Optional[Union[Payloads, bytes]] = None
            ) -> Any:
        if isinstance(target, str):
            target = self.contacts.get_actor_profile(target)
        receiver = target.address
        try:
            res = self._send_message_impl(receiver, name, tags, args or MyArgs(), payloads or MyPayloads())
            res.raise_for_status()
            try:
                return json.loads(res.text)
            except ValueError:
                return load_bytes(res.content)

        except TypeError:
            raise ProcedureInvokerError(f'failed to send message to {target.name}/{name}') from None

        except requests.ConnectionError:
            raise MsgConnectionError(f'connection failed or invalid message component channel') from None

        except requests.HTTPError as e:
            status = e.response.status_code
            if status == 400:
                raise InvocationAbortError(f'message call is not accepted: {e.response.text}') from None
            elif status == 401:
                raise InvalidInvokerError(f'current client not identified by receiver') from None
            elif status == 404:
                raise ProcedureNotFoundError(f'invalid message component channel') from None
            elif status == 410:
                redirect_name = e.response.text
                return self.invoke_procedure(redirect_name, name, tags, args, payloads)
            elif status == 412:
                raise InvocationRefusedError(e.response.text) from None
            raise InvocationFailedError(e.response.text) from None

    def _send_message_impl(
            self, address: str, path: str,
            tags: Optional[Tags], args: Args, payloads: Optional[Union[Payloads, bytes]]):
        """ This function does not raise for the response status. """
        url = f'http://{address}/{path}'    # noqa: https
        headers = {'from': self.local_name}
        if tags:
            insert_tags(headers, tags)
        files: dict[str, Any] = {'_args_': BytesIO(pickle.dumps(args))}
        if isinstance(payloads, (bytes, bytearray, memoryview)):
            headers['payloads-pre-pickled'] = '1'
            files['_payloads_'] = BytesIO(payloads)
        elif payloads is not None:
            for key, value in payloads.items():
                if isinstance(value, IOBase):   # file-like
                    files[key] = value
                elif isinstance(value, bytes):  # bytes, using BytesIO
                    files[key] = BytesIO(value)
                else:   # regular object, using pickle and BytesIO
                    files[key] = BytesIO(pickle.dumps(value))
        response = requests.post(url, files=files, headers=headers)
        return response

    def handshake(self, target: Union[str, ActorProfile]):
        if isinstance(target, str):
            target = self.contacts.get_actor_profile(target)
        try:
            url = f'http://{target.address}/__HANDSHAKE'
            res = requests.post(url, json={'name': self.local_name, 'address': self.local_address})
            res.raise_for_status()
        except Exception as e:
            raise HandshakeError(target) from e
        self.logger.info(f'handshake with {target.name} success')
    
    def handwave(self, target: Union[str, ActorProfile]):
        if isinstance(target, str):
            target = self.contacts.get_actor_profile(target)
        try:
            url = f'http://{target.address}/__HANDWAVE'
            res = requests.post(url, json={'name': self.local_name})
            res.raise_for_status()
        except Exception as e:
            raise HandwaveError(target) from e
        self.logger.info(f'handwave with {target.name} success')
