from typing import Optional

from roleml.core.actor.base import BaseActor
from roleml.core.actor.default.managers.element import ElementManager
from roleml.core.actor.default.managers.event import EventManager
from roleml.core.actor.default.managers.runnable import RunnableManager
from roleml.core.actor.default.managers.service import ServiceManager
from roleml.core.actor.default.managers.task import TaskManager
from roleml.core.actor.default.native import NativeRole
from roleml.core.actor.group.base import CollectiveImplementor
from roleml.core.context import ActorProfile, Context
from roleml.core.messaging.base import ProcedureInvoker, ProcedureProvider
from roleml.core.role.base import Role
from roleml.shared.aop import set_logger as set_aop_logger

__all__ = ['Actor']


class Actor(BaseActor):

    def __init__(self, profile: ActorProfile, *, context: Optional[Context] = None,
                 procedure_invoker: ProcedureInvoker, procedure_provider: ProcedureProvider,
                 collective_implementor: CollectiveImplementor,
                 handshakes: Optional[list[str]] = None):
        super().__init__(profile, context=context,
                         procedure_invoker=procedure_invoker, procedure_provider=procedure_provider,
                         collective_implementor=collective_implementor, handshakes=handshakes)
        set_aop_logger('roleml.aop')

        init_args = (self.ctx, self.thread_manager, self.role_status_manager, procedure_invoker, procedure_provider)
        self.runnable_manager = RunnableManager(*init_args)     # stop Runnable first when terminating
        self.service_manager = ServiceManager(*init_args)
        self.task_manager = TaskManager(*init_args)
        self.event_manager = EventManager(*init_args)
        self.element_manager = ElementManager(*init_args)

        self.native_role = NativeRole()
        self.add_role('actor', self.native_role)
        self.ctx.relationships.add_to_relationship('/', self.native_role.id)

    def _add_role_to_managers(self, role: Role):
        super()._add_role_to_managers(role)
        if role.name != 'actor':
            self.runnable_manager.add_role(role)
        # native role's run() executes in actor's main thread

    def run(self):
        super().run()
        self.native_role.run()

    def stop(self):
        self.native_role.stop()
        super().stop()
