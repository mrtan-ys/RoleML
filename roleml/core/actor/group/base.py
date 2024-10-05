from abc import ABC, abstractmethod
from typing import Any, Callable, Iterable, Mapping, TYPE_CHECKING, Optional

from roleml.core.actor.group.helpers import ErrorHandlingStrategy
from roleml.core.context import RoleInstanceID
from roleml.core.role.types import Message, TaskInvocation

if TYPE_CHECKING:
    from roleml.core.actor.base import BaseActor

__all__ = ['CollectiveImplementor']


class CollectiveImplementor(ABC):

    actor: 'BaseActor'

    def initialize(self, actor: 'BaseActor'):
        self.actor = actor

    @abstractmethod
    def call(self, instance_name: str, targets: Iterable[RoleInstanceID], channel_name: str, *,
             message_map: Optional[Mapping[RoleInstanceID, Message]] = None,
             # for broadcast and scatter respectively; choose one to provide if necessary; do not provide both
             message: Optional[Message] = None, messages: Optional[Iterable[Message]] = None,
             on_result: Optional[Callable[[RoleInstanceID, Any], Any]] = None,
             on_error: ErrorHandlingStrategy = ErrorHandlingStrategy.IGNORE,
             on_error_cb: Optional[Callable[[RoleInstanceID, Exception], Any]] = None,
             should_retry: Optional[Callable[[RoleInstanceID, Exception], bool]] = None
             ) -> Iterable[tuple[RoleInstanceID, Any]]:
        """ When determining the message to send to a target, the implementor will first search for a match item in
        ``message_map``. If that does not exist, the implementor will use either ``message`` or an item in ``messages``.
        The user should only choose one from ``message`` and ``messages`` to specify. """
        # this is some low-level APIs, but it is safe to leave most options default
        ...

    @abstractmethod
    def call_task(self, instance_name: str, targets: Iterable[RoleInstanceID], channel_name: str, *,
                  message_map: Optional[Mapping[RoleInstanceID, Message]] = None,
                  # for broadcast and scatter respectively; choose one to provide if necessary; do not provide both
                  message: Optional[Message] = None, messages: Optional[Iterable[Message]] = None,
                  on_call_error: ErrorHandlingStrategy = ErrorHandlingStrategy.IGNORE,
                  on_result: Optional[Callable[[RoleInstanceID, TaskInvocation], Any]] = None,
                  should_retry: Optional[Callable[[RoleInstanceID, Exception], bool]] = None):
        """ When determining the message to send to a target, the implementor will first search for a match item in
        ``message_map``. If that does not exist, the implementor will use either ``message`` or an item in ``messages``.
        The user should only choose one from ``message`` and ``messages`` to specify. """
        ...
