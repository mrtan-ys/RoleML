from typing import Any, Callable, Iterable, Mapping, Optional, Union
from typing_extensions import override

import fasteners

from roleml.core.actor.base import BaseActor
from roleml.core.actor.default.managers.element import ElementManager
from roleml.core.actor.default.managers.runnable import RunnableManager
from roleml.core.actor.group.base import CollectiveImplementor
from roleml.core.actor.group.helpers import ErrorHandlingStrategy
from roleml.core.context import ActorProfile, Context, RoleInstanceID
from roleml.core.messaging.base import ProcedureInvoker, ProcedureProvider
from roleml.core.messaging.types import Args, Payloads
from roleml.core.role.base import Role
from roleml.core.role.exceptions import NoSuchRoleError
from roleml.core.role.types import EventSubscriptionMode, Message, TaskInvocation
from roleml.extensions.containerization.runtime.managers.event import EventManager
from roleml.extensions.containerization.runtime.managers.status import StatusManager
from roleml.extensions.containerization.runtime.managers.service import ServiceManager
from roleml.extensions.containerization.runtime.managers.task import TaskManager
from roleml.extensions.containerization.runtime.native import NativeRole
from roleml.extensions.containerization.runtime.wrapper import ContextProxy
from roleml.shared.aop import set_logger as set_aop_logger

__all__ = ["RoleRuntime"]


def _locked_messaging_methods(method):
    def wrapper(self: "RoleRuntime", *args, **kwargs):
        with self.communication_lock.read_lock():
            return method(self, *args, **kwargs)

    return wrapper


class RoleRuntime(BaseActor):

    def __init__(
        self,
        profile: ActorProfile,
        *,
        context: Optional[Context] = None,
        procedure_invoker: ProcedureInvoker,
        procedure_provider: ProcedureProvider,
        collective_implementor: CollectiveImplementor,
        handshakes: Optional[list[str]] = None,
    ):
        if context is None:
            context = Context.build(profile)
        if not isinstance(context, ContextProxy):
            context = ContextProxy(context)   # type: ignore
        super().__init__(
            profile,
            context=context,
            procedure_invoker=procedure_invoker,
            procedure_provider=procedure_provider,
            collective_implementor=collective_implementor,
            handshakes=handshakes,
        )
        set_aop_logger("roleml.aop")

        init_args = (
            self.ctx,
            self.thread_manager,
            self.role_status_manager,
            procedure_invoker,
            procedure_provider,
        )
        self.runnable_manager = RunnableManager(
            *init_args
        )  # stop Runnable first when terminating
        self.service_manager = ServiceManager(*init_args)
        self.task_manager = TaskManager(*init_args)
        self.event_manager = EventManager(*init_args)
        self.element_manager = ElementManager(*init_args)

        self.communication_lock = fasteners.ReaderWriterLock()
        self.offload_manager = StatusManager(
            *init_args, communication_lock=self.communication_lock
        )

        self.native_role = NativeRole()
        self.add_role("actor", self.native_role)

        self.ctx.relationships.add_to_relationship(
            "/", RoleInstanceID(self.profile.name, "actor")
        )
        # add node controller' s actor to 'manager' relationships to allow control messages
        # TODO: currently, node controller' s name is same as runtime's name. Maybe we should change it.
        self.ctx.relationships.add_to_relationship(
            "manager",
            RoleInstanceID(profile.name, "actor"),
        )

        self._actor_started_callback: list[Callable[[], Any]] = []

    def change_controller(self, new_profile: ActorProfile, old_profile: ActorProfile):
        assert self.profile.name == old_profile.name

        # 下面两段都是为了兼容运行在127.0.0.1的情况
        # the contact of original node controller is not the same as `old_profile`
        # the former is the intra address of the docker network such as `host.docker.internal:5555`
        # while `old_profile.address` is the outside address such as `192.168.1.111:5555`
        # So we need to update the address in the contact.
        self.ctx.contacts.add_contact(old_profile)
        old_controller_internal_ip = self.ctx.contacts.get_actor_profile(
            old_profile.name
        ).address.split(":")[0]
        old_controller_outside_ip = old_profile.address.split(":")[0]
        for profile in list(
            self.ctx.contacts.all_actors()
        ):  # copy to avoid modifying the dict while iterating
            ip, port = profile.address.split(":")
            if ip == old_controller_internal_ip:
                self.ctx.contacts.add_contact(
                    ActorProfile(profile.name, f"{old_controller_outside_ip}:{port}")
                )

        new_controller_internal_ip = new_profile.address.split(":")[0]
        new_controller_outside_ip = self.ctx.contacts.get_actor_profile(
            new_profile.name
        ).address.split(":")[0]
        for profile in list(self.ctx.contacts.all_actors()):
            ip, port = profile.address.split(":")
            if ip == new_controller_outside_ip:
                self.ctx.contacts.add_contact(
                    ActorProfile(profile.name, f"{new_controller_internal_ip}:{port}")
                )

        # replace controller's contact with new one
        self.ctx.contacts.add_contact(new_profile)

        self.ctx.relationships.remove_from_relationship(
            "manager", *self.ctx.relationships.get_relationship("manager")
        )
        self.ctx.relationships.add_to_relationship(
            "manager",
            RoleInstanceID(new_profile.name, "actor"),
        )

        self.procedure_invoker.local_name = new_profile.name

        assert isinstance(self.ctx, ContextProxy)
        # keep the address unchanged
        new_profile = self.ctx.profile._replace(name=new_profile.name)
        self.ctx.update_context_object(self.ctx._context._replace(profile=new_profile))

    @override
    def _add_role_to_managers(self, role: Role):
        super()._add_role_to_managers(role)
        if role.name != "actor":
            self.runnable_manager.add_role(role)
        # native role's run() executes in actor's main thread

    def add_actor_started_callback(self, callback: Callable[[], Any]):
        self._actor_started_callback.append(callback)

    @override
    def run(self):
        super().run()
        for callback in self._actor_started_callback:
            callback()
        self.native_role.run()

    @override
    def stop(self):
        self.native_role.stop()
        super().stop()

    @override
    def convert_relationship_to_instance(
        self, relationship_name: str
    ) -> RoleInstanceID:
        target_instance = None
        for target_instance in self.ctx.relationships.get_relationship(
            relationship_name
        ):
            break
        # in containerized mode, implicit relationship is not supported
        if target_instance is None:
            self.logger.error(
                f"No role in relationship: {relationship_name}. "
                "Roles should be explicitly added to the relationship in containerized mode. "
                "Please check the relationship configuration."
            )
            raise NoSuchRoleError(f"No role in relationship: {relationship_name}")
        return target_instance

    @override
    @_locked_messaging_methods
    def call(
        self,
        instance_name: str,
        target: Union[str, RoleInstanceID],
        channel_name: str,
        message: Message,
    ) -> Any:
        return super().call(instance_name, target, channel_name, message)

    @override
    @_locked_messaging_methods
    def call_group(
        self,
        instance_name: str,
        group: Iterable[RoleInstanceID],
        channel_name: str,
        *,
        message_map: Optional[Mapping[RoleInstanceID, Message]] = None,
        # choose one to provide if necessary; do not provide both
        message: Optional[Message] = None,
        messages: Optional[Iterable[Message]] = None,
        on_result: Optional[Callable[[RoleInstanceID, Any], Any]] = None,
        on_error: ErrorHandlingStrategy = ErrorHandlingStrategy.RAISE_FIRST,
    ) -> Iterable[tuple[RoleInstanceID, Any]]:
        return super().call_group(
            instance_name,
            group,
            channel_name,
            message=message,
            message_map=message_map,
            messages=messages,
            on_result=on_result,
            on_error=on_error,
        )

    @override
    @_locked_messaging_methods
    def call_task(
        self,
        instance_name: str,
        target: Union[str, RoleInstanceID],
        channel_name: str,
        message: Message,
    ) -> TaskInvocation:
        return super().call_task(instance_name, target, channel_name, message)

    @override
    @_locked_messaging_methods
    def call_task_group(
        self,
        instance_name: str,
        group: Iterable[RoleInstanceID],
        channel_name: str,
        *,
        message_map: Optional[Mapping[RoleInstanceID, Message]] = None,
        # choose one to provide if necessary; do not provide both
        message: Optional[Message] = None,
        messages: Optional[Iterable[Message]] = None,
        on_call_error: ErrorHandlingStrategy = ErrorHandlingStrategy.RAISE_FIRST,
        on_result: Optional[Callable[[RoleInstanceID, TaskInvocation], Any]] = None,
    ):
        return super().call_task_group(
            instance_name,
            group,
            channel_name,
            message=message,
            message_map=message_map,
            messages=messages,
            on_call_error=on_call_error,
            on_result=on_result,
        )

    @override
    @_locked_messaging_methods
    def subscribe(
        self,
        instance_name: str,
        target: RoleInstanceID,
        channel_name: str,
        handler: Callable[[RoleInstanceID, Args, Payloads], Any],
        *,
        conditions: Optional[dict[str, Any]] = None,
        mode: EventSubscriptionMode = "forever",
    ):
        return super().subscribe(
            instance_name,
            target,
            channel_name,
            handler,
            conditions=conditions,
            mode=mode,
        )

    @override
    @_locked_messaging_methods
    def unsubscribe(
        self, instance_name: str, target: RoleInstanceID, channel_name: str
    ):
        return super().unsubscribe(instance_name, target, channel_name)

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
