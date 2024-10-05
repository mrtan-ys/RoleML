from typing import Optional
from typing_extensions import override
from roleml.core.actor.base import BaseActor
from roleml.core.actor.default.managers.element import ElementManager
from roleml.core.actor.default.managers.runnable import RunnableManager
# from roleml.core.actor.default.native import NativeRole
from roleml.core.actor.group.base import CollectiveImplementor
from roleml.core.context import ActorProfile, Context, RoleInstanceID
from roleml.core.messaging.base import ProcedureInvoker, ProcedureProvider
from roleml.core.role.base import Role
from roleml.core.role.types import Message
from roleml.extensions.containerization.builders.spec import ContainerizationConfig
from roleml.extensions.containerization.controller.managers.log import LogManager
from roleml.extensions.containerization.controller.roles.native import NativeRole
from roleml.extensions.containerization.controller.managers.container import ContainerManager
from roleml.extensions.containerization.controller.managers.event import EventManager
from roleml.extensions.containerization.controller.managers.service import ServiceManager
from roleml.extensions.containerization.controller.managers.task import TaskManager
from roleml.extensions.containerization.controller.roles.offloading_executor.base import OffloadingExecutor
from roleml.extensions.containerization.controller.roles.prober.base import ResourceProber
from roleml.shared.aop import set_logger as set_aop_logger


__all__ = ['NodeController']


class NodeController(BaseActor):

    def __init__(self, profile: ActorProfile, *, context: Optional[Context] = None,
                 procedure_invoker: ProcedureInvoker, procedure_provider: ProcedureProvider,
                 collective_implementor: CollectiveImplementor,
                 handshakes: Optional[list[str]] = None,
                 containerization_config: ContainerizationConfig,):
        super().__init__(profile, context=context,
                         procedure_invoker=procedure_invoker, procedure_provider=procedure_provider,
                         collective_implementor=collective_implementor, handshakes=handshakes)
        set_aop_logger('roleml.aop')

        self.containerization_config = containerization_config
        self.containerization_config.temp_dir.mkdir(parents=True, exist_ok=True)

        init_args = (self.ctx, self.thread_manager, self.role_status_manager, procedure_invoker, procedure_provider)
        self.runnable_manager = RunnableManager(*init_args)     # stop Runnable first when terminating
        self.service_manager = ServiceManager(*init_args)
        self.task_manager = TaskManager(*init_args)
        self.event_manager = EventManager(*init_args)
        self.element_manager = ElementManager(*init_args)
        self.container_manager = ContainerManager(*init_args, containerization_config=containerization_config)
        self.log_manager = LogManager(*init_args)

        self.native_role = NativeRole()
        self.add_role('actor', self.native_role)
        self.ctx.relationships.add_to_relationship('/', self.native_role.id)

        # avoid `actor not identified` error
        # TODO this is a workaround
        self.ctx.contacts.add_contact(self.profile)

        # self.resource_prober_role = ResourceProber()
        # self.add_role('resource_prober', self.resource_prober_role)

        self.offload_executor_role = OffloadingExecutor()
        self.add_role('offloading_executor', self.offload_executor_role)

    @override
    def _add_role_to_managers(self, role: Role):
        super()._add_role_to_managers(role)
        # native role's run() executes in actor's main thread
        if role.name != 'actor':
            self.runnable_manager.add_role(role)
        if role.name not in ('actor', 'resource_prober', 'offloading_executor'):
            self.container_manager.add_role(role)

    @override
    def run(self):
        super().run()
        self.native_role.run()

    @override
    def stop(self):
        self.native_role.stop()
        super().stop()

    def get_containerized_role_id(self, container: str, role: str = 'actor') -> RoleInstanceID:
        return RoleInstanceID(f"{self.profile.name}_{container}", role)

    def update_instance_id(
        self, old_instance_id: RoleInstanceID, new_instance_id: RoleInstanceID
    ):
        for r_name, roles in self.ctx.relationships.all_relationships().items():
            for role_id in roles:
                if role_id == old_instance_id:
                    self.ctx.relationships.remove_from_relationship(r_name, role_id)
                    self.ctx.relationships.add_to_relationship(r_name, new_instance_id)

        assert isinstance(self.task_manager, TaskManager)
        self.task_manager.update_instance_id(old_instance_id, new_instance_id)
        assert isinstance(self.event_manager, EventManager)
        self.event_manager.update_instance_id(old_instance_id, new_instance_id)
