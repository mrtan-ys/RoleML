import logging
from abc import ABC, abstractmethod

from roleml.core.actor.status import RoleStatusManager
from roleml.core.context import Context
from roleml.core.messaging.base import ProcedureInvoker, ProcedureProvider
from roleml.core.role.base import Role
from roleml.shared.multithreading.management import ThreadManager

__all__ = ['BaseManager']


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
