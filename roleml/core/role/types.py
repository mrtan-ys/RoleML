from typing import Any, ClassVar, Literal, NamedTuple, Optional, Protocol, runtime_checkable

from roleml.core.messaging.types import Args, Payloads, MyArgs, MyPayloads

__all__ = ['Args', 'Payloads', 'MyArgs', 'MyPayloads', 'Message',
           'TaskInvocation', 'EventSubscriptionMode', 'PluginAttribute']


class Message(NamedTuple):
    """ Encapsulating a message for service/task call or event emission. """

    args: Args = {}
    payloads: Payloads = {}

    @staticmethod
    def empty():
        return Message({}, {})


@runtime_checkable
class TaskInvocation(Protocol):

    def result(self, timeout: Optional[float] = None) -> Any: ...

    def exception(self, timeout: Optional[float] = None) -> Optional[Exception]: ...

    def add_done_callback(self, func): ...


EventSubscriptionMode = Literal['once', 'forever']


class PluginAttribute:

    PLUGIN_NAME: ClassVar[str] = 'unknown'

    def __init_subclass__(cls):
        if hasattr(cls, 'PLUGIN_NAME'):
            setattr(cls, 'PLUGIN_NAME', cls.__name__)
