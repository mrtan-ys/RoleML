from typing import Any, Callable, Iterable, Mapping, Optional, Union
from typing_extensions import override

from roleml.core.actor.group.helpers import ErrorHandlingStrategy
from roleml.core.builders.role import RoleConfig
from roleml.core.context import RoleInstanceID
from roleml.core.role.base import Role
from roleml.core.role.types import Args, EventSubscriptionMode, Message, Payloads, TaskInvocation


class ContainerizedRole(Role):

    def __init__(self, config: RoleConfig):
        super().__init__()
        self._should_stop = False
        self.config = config

    @override
    def call(self, target: Union[str, RoleInstanceID], channel_name: str,
             args: Optional[Args] = None, payloads: Optional[Payloads] = None, *, message: Optional[Message] = None
             ) -> Any:
        raise NotImplementedError()

    @override
    def call_group(
            self, group: Iterable[RoleInstanceID], channel_name: str,
            args: Optional[Args] = None, payloads: Optional[Payloads] = None, *,
            message_map: Optional[Mapping[RoleInstanceID, Message]] = None, 
            message: Optional[Message] = None, messages: Optional[Iterable[Message]] = None,
            on_result: Optional[Callable[[RoleInstanceID, Any], Any]] = None,
            on_error: ErrorHandlingStrategy = ErrorHandlingStrategy.RAISE_FIRST
    ) -> Iterable[tuple[RoleInstanceID, Any]]:
        raise NotImplementedError()

    @override
    def call_task(self, target: Union[str, RoleInstanceID], channel_name: str,
                  args: Optional[Args] = None, payloads: Optional[Payloads] = None, *, message: Optional[Message] = None
                  ) -> TaskInvocation:
        raise NotImplementedError()

    @override
    def call_task_group(
            self, group: Iterable[RoleInstanceID], channel_name: str,
            args: Optional[Args] = None, payloads: Optional[Payloads] = None, *,
            message_map: Optional[Mapping[RoleInstanceID, Message]] = None, 
            message: Optional[Message] = None, messages: Optional[Iterable[Message]] = None,
            on_call_error: ErrorHandlingStrategy = ErrorHandlingStrategy.RAISE_FIRST,
            on_result: Optional[Callable[[RoleInstanceID, TaskInvocation], Any]] = None):
        raise NotImplementedError()

    @override
    def subscribe(self, target: RoleInstanceID, channel_name: str,
                  handler: Callable[[RoleInstanceID, Args, Payloads], Any], *,
                  conditions: Optional[dict[str, Any]] = None, mode: EventSubscriptionMode = 'forever'):
        raise NotImplementedError()

    @override
    def unsubscribe(self, target: RoleInstanceID, channel_name: str):
        raise NotImplementedError()
