from typing import Any, Optional, Union

from roleml.core.context import ActorProfile
from roleml.core.messaging.base import ProcedureInvoker, ProcedureProvider
from roleml.core.messaging.types import Args, Payloads, Tags

__all__ = ['ProcedureInvokerDisabled', 'ProcedureProviderDisabled', 'MessagingComponentDisabled']


class ProcedureInvokerDisabled(ProcedureInvoker):

    def invoke_procedure(
            self, target: Union[str, ActorProfile], name: str,
            tags: Optional[Tags] = None, args: Optional[Args] = None, payloads: Optional[Union[Payloads, bytes]] = None
            ) -> Any:
        raise RuntimeError('cannot send message to another actor since the procedure invoker is disabled')

    handshake = None        # type: ignore
    handwave = None         # type: ignore


class ProcedureProviderDisabled(ProcedureProvider):

    supports_handshake_handwave = False

    def add_procedure(self, name, handler):
        pass

    def run(self):
        pass


class MessagingComponentDisabled(ProcedureInvokerDisabled, ProcedureProviderDisabled):
    pass
