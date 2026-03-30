from abc import ABC, abstractmethod
from typing import Any, Callable, Optional, Union

from roleml.core.actor.helpers import PayloadsPickledMessage
from roleml.core.actor.manager.base import BaseManager
from roleml.core.context import RoleInstanceID
from roleml.core.role.types import Args, EventSubscriptionMode, Message, Payloads, TaskInvocation


class BaseServiceManager(BaseManager, ABC):

    @abstractmethod
    def call(self, instance_name: str, target: RoleInstanceID, channel_name: str,
             message: Union[Message, PayloadsPickledMessage]) -> Any:
        ...


class BaseTaskManager(BaseManager, ABC):

    @abstractmethod
    def call_task(self, instance_name: str, target: RoleInstanceID, channel_name: str,
                  message: Union[Message, PayloadsPickledMessage]) -> TaskInvocation:
        ...


class BaseEventManager(BaseManager, ABC):

    @abstractmethod
    def emit(self, instance_name: str, channel_name: str, message: Message):
        ...

    @abstractmethod
    def subscribe(self, instance_name: str, target: RoleInstanceID, channel_name: str,
                  handler: Callable[[RoleInstanceID, Args, Payloads], Any], *,
                  conditions: Optional[dict[str, Any]] = None, mode: EventSubscriptionMode = 'forever'):
        ...

    @abstractmethod
    def unsubscribe(self, instance_name: str, target: RoleInstanceID, channel_name: str):
        ...
