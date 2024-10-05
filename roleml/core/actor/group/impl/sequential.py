from typing import Any, Callable, Iterable, Mapping, Optional

from roleml.core.actor.group.base import CollectiveImplementor
from roleml.core.actor.group.helpers import ErrorHandlingStrategy
from roleml.core.actor.group.impl.helpers import ServiceCallPerformer, TaskCallPerformer
from roleml.core.context import RoleInstanceID
from roleml.core.role.types import Message, TaskInvocation

__all__ = ['SequentialCollectiveImplementor']


class SequentialCollectiveImplementor(CollectiveImplementor):

    def call(self, instance_name: str, targets: Iterable[RoleInstanceID], channel_name: str, *,
             message_map: Optional[Mapping[RoleInstanceID, Message]] = None,
             # for broadcast and scatter respectively; choose one to provide if necessary; do not provide both
             message: Optional[Message] = None, messages: Optional[Iterable[Message]] = None,
             on_result: Optional[Callable[[RoleInstanceID, Any], Any]] = None,
             on_error: ErrorHandlingStrategy = ErrorHandlingStrategy.IGNORE,
             on_error_cb: Optional[Callable[[RoleInstanceID, Exception], Any]] = None,
             should_retry: Optional[Callable[[RoleInstanceID, Exception], bool]] = None
             ) -> Iterable[tuple[RoleInstanceID, Any]]:
        performer = ServiceCallPerformer(
            self.actor.profile.name, instance_name, channel_name, self.actor.service_manager,
            message=message, message_map=message_map, messages=messages,
            on_error=on_error, on_result=on_result, on_error_cb=on_error_cb, should_retry=should_retry)
        for target in targets:
            result = performer.call(target)
            yield target, result

    def call_task(self, instance_name: str, targets: Iterable[RoleInstanceID], channel_name: str, *,
                  message_map: Optional[Mapping[RoleInstanceID, Message]] = None,
                  # for broadcast and scatter respectively; choose one to provide if necessary; do not provide both
                  message: Optional[Message] = None, messages: Optional[Iterable[Message]] = None,
                  on_call_error: ErrorHandlingStrategy = ErrorHandlingStrategy.IGNORE,
                  on_result: Optional[Callable[[RoleInstanceID, TaskInvocation], Any]] = None,
                  should_retry: Optional[Callable[[RoleInstanceID, Exception], bool]] = None):
        performer = TaskCallPerformer(
            self.actor.profile.name, instance_name, channel_name, self.actor.task_manager,
            message=message, message_map=message_map, messages=messages,
            on_call_error=on_call_error, on_result=on_result, should_retry=should_retry)
        for target in targets:
            performer.call_task(target)
