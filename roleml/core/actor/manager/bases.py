import logging
from abc import ABC, abstractmethod
from typing import Any, Callable, Optional, Union

from roleml.core.actor.helpers import PayloadsPickledMessage
from roleml.core.actor.status import RoleStatusManager
from roleml.core.context import Context, RoleInstanceID
from roleml.core.messaging.base import ProcedureInvoker, ProcedureProvider
from roleml.core.role.base import Role
from roleml.core.role.elements import ElementImplementation
from roleml.core.role.types import Message, Args, Payloads, TaskInvocation, EventSubscriptionMode
from roleml.shared.multithreading.management import ThreadManager

__all__ = ['BaseManager',
           'BaseServiceManager', 'BaseTaskManager', 'BaseEventManager', 'BaseElementManager',
           'BaseRunnableManager']


class BaseManager(ABC):

    def __init__(self, context: Context, thread_manager: ThreadManager, role_status_manager: RoleStatusManager,
                 procedure_invoker: ProcedureInvoker, procedure_provider: ProcedureProvider, **kwargs):
        self.context = context
        self.thread_manager = thread_manager
        self.role_status_manager = role_status_manager
        self.procedure_invoker = procedure_invoker
        self.procedure_provider = procedure_provider
        self.logger = logging.getLogger()
        self.initialize(**kwargs)   # noqa: kwargs defined by subclass

    def initialize(self):
        pass

    @abstractmethod
    def add_role(self, role: Role): ...


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


class BaseElementManager(BaseManager, ABC):

    @abstractmethod
    def implement_element(self, instance_name: str, element_name: str, impl: ElementImplementation):
        ...


class BaseRunnableManager(BaseManager, ABC):
    pass
