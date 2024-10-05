import logging
from abc import ABC, abstractmethod
from typing import Any, Optional, Union

from roleml.core.context import Contacts, ActorProfile
from roleml.core.messaging.types import Args, Payloads, Tags, MessageHandler
from roleml.shared.interfaces import Runnable


class ProcedureInvoker(ABC):

    def __init__(self, local_name: str, local_address: str, contacts: Contacts):
        self.local_name = local_name
        self.local_address = local_address
        self.contacts = contacts
        self.logger = logging.getLogger('roleml.messaging.procedure-invoker')

    @abstractmethod
    def invoke_procedure(
            self, target: Union[str, ActorProfile], name: str,
            tags: Optional[Tags] = None, args: Optional[Args] = None, payloads: Optional[Union[Payloads, bytes]] = None
            ) -> Any:
        """ If `payloads` is a bytes object, it must be a pickled `dict[str, Any]` of original payloads. """
        ...
    
    def handshake(self, target: Union[str, ActorProfile]) -> None:
        raise RuntimeError('the current procedure invoker does not support handshake')
    
    def handwave(self, target: Union[str, ActorProfile]) -> None:
        raise RuntimeError('the current procedure invoker does not support handwave')


class ProcedureProvider(Runnable, ABC):

    supports_handshake_handwave: bool = False

    def __init__(self, local_name: str, local_address: str, contacts: Contacts):
        self.local_name = local_name
        self.local_address = local_address
        self.contacts = contacts
        self.logger = logging.getLogger('roleml.messaging.procedure-provider')

    @abstractmethod
    def add_procedure(self, name: str, handler: MessageHandler): ...


class MessagingComponent(ProcedureInvoker, ProcedureProvider, ABC):
    pass
