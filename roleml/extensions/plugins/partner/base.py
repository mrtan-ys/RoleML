from typing import Any, Callable, Iterable, Mapping, Optional, TYPE_CHECKING

from roleml.core.actor.group.helpers import ErrorHandlingStrategy
from roleml.core.context import RoleInstanceID
from roleml.core.messaging.types import Args, Payloads
from roleml.core.role.types import Message, TaskInvocation, PluginAttribute

if TYPE_CHECKING:
    from roleml.core.role.base import Role


class Partner(PluginAttribute):

    PLUGIN_NAME = 'partner'

    __slots__ = ('relationship_name', '_base')

    def __init__(self, relationship_name: str):
        self.relationship_name: str = relationship_name
        self._base: 'Role' = None       # type: ignore  # to be filled by actor

    @property
    def base(self) -> 'Role':
        if not self._base:
            raise RuntimeError('cannot use partner when role is not initialized')
        return self._base

    @base.setter
    def base(self, base: 'Role'):
        self._base = base

    def service(self, channel_name: str,
                args: Optional[Args] = None, payloads: Optional[Payloads] = None, *, message: Optional[Message] = None
                ) -> Any:
        return self.base.call(self.relationship_name, channel_name, args, payloads, message=message)

    def service_all(
        self, channel_name: str,
        args: Optional[Args] = None, payloads: Optional[Payloads] = None, *,
        message_map: Optional[Mapping[RoleInstanceID, Message]] = None,
        message: Optional[Message] = None, messages: Optional[Iterable[Message]] = None,
        on_result: Optional[Callable[[RoleInstanceID, Any], Any]] = None,
        on_error: ErrorHandlingStrategy = ErrorHandlingStrategy.RAISE_FIRST
    ) -> Iterable[tuple[RoleInstanceID, Any]]:
        return self.base.call_group(list(self.instances), channel_name, args, payloads, message=message,
                                    message_map=message_map, messages=messages, on_result=on_result, on_error=on_error)

    def task(self, channel_name: str,
             args: Optional[Args] = None, payloads: Optional[Payloads] = None, *, message: Optional[Message] = None
             ) -> TaskInvocation:
        return self.base.call_task(self.relationship_name, channel_name, args, payloads, message=message)

    def task_all(
            self, channel_name: str,
            args: Optional[Args] = None, payloads: Optional[Payloads] = None, *,
            message_map: Optional[Mapping[RoleInstanceID, Message]] = None,
            message: Optional[Message] = None, messages: Optional[Iterable[Message]] = None,
            on_call_error: ErrorHandlingStrategy = ErrorHandlingStrategy.RAISE_FIRST,
            on_result: Optional[Callable[[RoleInstanceID, TaskInvocation], Any]] = None):
        self.base.call_task_group(list(self.instances), channel_name, args, payloads, message=message,
                                  message_map=message_map, messages=messages,
                                  on_call_error=on_call_error, on_result=on_result)

    @property
    def instances(self) -> Iterable[RoleInstanceID]:
        return self.base.ctx.relationships.get_relationship(self.relationship_name)
