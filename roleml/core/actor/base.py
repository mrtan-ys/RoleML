import logging
from threading import RLock
from typing import Any, Callable, Iterable, Mapping, Optional, Union

from roleml.core.actor.group.base import CollectiveImplementor
from roleml.core.actor.group.helpers import ErrorHandlingStrategy
from roleml.core.actor.manager.bases import BaseServiceManager, BaseTaskManager, BaseEventManager, BaseElementManager
from roleml.core.actor.status import RoleStatusManager
from roleml.core.context import ActorProfile, Context, RoleInstanceID
from roleml.core.messaging.base import ProcedureInvoker, ProcedureProvider
from roleml.core.messaging.types import Args, Payloads
from roleml.core.role.base import Role
from roleml.core.role.elements import ElementImplementation
from roleml.core.role.naming import to_standardized_name
from roleml.core.role.types import Message, TaskInvocation, EventSubscriptionMode
from roleml.core.status import Status, StatusTransferCallbackError
from roleml.shared.interfaces import Runnable
from roleml.shared.multithreading.management import ThreadManager


class BaseActor(Runnable):

    # the following managers must be initialized by subclass
    service_manager: BaseServiceManager
    task_manager: BaseTaskManager
    event_manager: BaseEventManager
    element_manager: BaseElementManager

    logger: logging.Logger

    def __init__(self, profile: ActorProfile, *, context: Optional[Context] = None,
                 procedure_invoker: ProcedureInvoker, procedure_provider: ProcedureProvider,
                 collective_implementor: CollectiveImplementor,
                 handshakes: Optional[list[str]] = None):
        self.profile = profile
        self.ctx = context if context is not None else Context.build(profile)
        Context.set_active_context(self.ctx)
        self.logger = logging.getLogger('roleml.actor')

        self.thread_manager = ThreadManager()

        self.procedure_invoker = procedure_invoker
        self.procedure_provider = procedure_provider
        self.collective_implementor = collective_implementor
        collective_implementor.initialize(self)

        if handshakes:
            handshake_success = []
            for actor_name in handshakes:
                try:
                    procedure_invoker.handshake(actor_name)
                except Exception:
                    self.logger.error(f'error in handshake with {actor_name}')
                    self._handwave_with(self.ctx.handwaves)
                    raise
                else:
                    handshake_success.append(actor_name)
            del handshake_success

        self.management_lock = RLock()
        self.role_status_manager = RoleStatusManager()

    def add_role(self, instance_name: str, role: Role):
        with self.management_lock:
            self.role_status_manager.add_role(instance_name)    # raise if instance_name already exists
            role.attach(instance_name, self)
            try:
                self._add_role_to_managers(role)
                self.role_status_manager.ctrl(instance_name).declared(ignore_callback_error=False)
            except Exception as e:
                self.logger.error(f'failed to add role instance {instance_name}: {e!s}')
                raise
            else:
                self.logger.info(f'new role instance ({instance_name}) added')

    def _add_role_to_managers(self, role: Role):
        self.service_manager.add_role(role)
        self.task_manager.add_role(role)
        self.event_manager.add_role(role)
        self.element_manager.add_role(role)

    def start_role(self, instance_name: str):
        with self.management_lock:
            try:
                ctrl = self.role_status_manager.ctrl(instance_name)
            except KeyError:
                raise RuntimeError(f'no such role instance named {instance_name}')
            else:
                if ctrl.status == Status.DECLARED:
                    try:
                        ctrl.ready(ignore_callback_error=False)
                    except StatusTransferCallbackError:
                        self.logger.error(f'failed to start role instance {instance_name}, which will now terminate')
                        ctrl.terminate(force=True)
                        raise
                    else:
                        self.logger.info(f'role instance ({instance_name}) is READY')
                else:
                    raise RuntimeError(f'cannot start role instance {instance_name}')

    def stop_role(self, instance_name: str):
        with self.management_lock:
            try:
                ctrl = self.role_status_manager.ctrl(instance_name)
            except KeyError:
                raise RuntimeError(f'no such role instance named {instance_name}')
            else:
                ctrl.terminate(force=True)
                self.logger.info(f'role instance ({instance_name}) is TERMINATED')

    def run(self):
        """ Run the actor. This method should never be called more than once. """
        if isinstance(self.procedure_invoker, Runnable):
            self.thread_manager.add_threaded_component(self.procedure_invoker, start=True)
        if isinstance(self.procedure_provider, Runnable) and self.procedure_provider is not self.procedure_invoker:
            self.thread_manager.add_threaded_component(self.procedure_provider, start=True)

        with self.management_lock:
            self.logger.info('actor starts running')
            for name, ctrl in self.role_status_manager.ctrls.items():
                if ctrl.status == Status.DECLARED:
                    ctrl.ready()
                    self.logger.info(f'role instance ({name}) is READY')

    def stop(self):
        """ Stop the actor. This method should be called in another thread
        or put to `finally` when `run` is in a `try` block. """
        with self.management_lock:
            self.logger.info('actor about to stop, please wait for runnable roles to finish')
            for name in reversed(list(self.role_status_manager.ctrls.keys())):
                ctrl = self.role_status_manager.ctrl(name)
                ctrl.terminate(force=True)
                self.logger.info(f'role instance ({name}) is TERMINATED')
            self.thread_manager.terminate_all_components()
            self._handwave_with(self.ctx.handwaves)
            self.ctx.handwaves.clear()
            self.logger.info('actor now stopped')
    
    def handshake(self, actor_name: str):
        self.procedure_invoker.handshake(actor_name)

    def handwave(self, actor_name: str):
        self.procedure_invoker.handwave(actor_name)
    
    def _handwave_with(self, actor_names: list[str]):
        for actor_name in actor_names:
            try:
                self.procedure_invoker.handwave(actor_name)
            except Exception as e:
                self.logger.error(f'error in handwave with {actor_name}: {e}')

    # region proxy methods for service/task calls and event subscriptions, used by role

    def call(self, instance_name: str, target: Union[str, RoleInstanceID], channel_name: str, message: Message) -> Any:
        if isinstance(target, str):
            target = self.convert_relationship_to_instance(target)
        return self.service_manager.call(instance_name, target, channel_name, message)

    def call_group(self, instance_name: str, group: Iterable[RoleInstanceID], channel_name: str, *,
                   message_map: Optional[Mapping[RoleInstanceID, Message]] = None,
                   # choose one to provide if necessary; do not provide both
                   message: Optional[Message] = None, messages: Optional[Iterable[Message]] = None,
                   on_result: Optional[Callable[[RoleInstanceID, Any], Any]] = None,
                   on_error: ErrorHandlingStrategy = ErrorHandlingStrategy.RAISE_FIRST) \
            -> Iterable[tuple[RoleInstanceID, Any]]:
        return self.collective_implementor.call(instance_name, group, channel_name, message=message,
                                                message_map=message_map, messages=messages,
                                                on_result=on_result, on_error=on_error)

    def call_task(self, instance_name: str, target: Union[str, RoleInstanceID], channel_name: str, message: Message) \
            -> TaskInvocation:
        if isinstance(target, str):
            target = self.convert_relationship_to_instance(target)
        return self.task_manager.call_task(instance_name, target, channel_name, message)

    def call_task_group(self, instance_name: str, group: Iterable[RoleInstanceID], channel_name: str, *,
                        message_map: Optional[Mapping[RoleInstanceID, Message]] = None,
                        # choose one to provide if necessary; do not provide both
                        message: Optional[Message] = None, messages: Optional[Iterable[Message]] = None,
                        on_call_error: ErrorHandlingStrategy = ErrorHandlingStrategy.RAISE_FIRST,
                        on_result: Optional[Callable[[RoleInstanceID, TaskInvocation], Any]] = None):
        self.collective_implementor.call_task(instance_name, group, channel_name, message=message,
                                              message_map=message_map, messages=messages,
                                              on_call_error=on_call_error, on_result=on_result)

    def subscribe(self, instance_name: str, target: RoleInstanceID, channel_name: str,
                  handler: Callable[[RoleInstanceID, Args, Payloads], Any], *,
                  conditions: Optional[dict[str, Any]] = None, mode: EventSubscriptionMode = 'forever'):
        self.event_manager.subscribe(instance_name, target, channel_name, handler, conditions=conditions, mode=mode)

    def unsubscribe(self, instance_name: str, target: RoleInstanceID, channel_name: str):
        self.event_manager.unsubscribe(instance_name, target, channel_name)

    # endregion

    def implement_element(self, instance_name: str, element_name: str, impl: ElementImplementation):
        self.element_manager.implement_element(instance_name, to_standardized_name(element_name), impl)

    def convert_relationship_to_instance(self, relationship_name: str) -> RoleInstanceID:
        target_instance = None
        for target_instance in self.ctx.relationships.get_relationship(relationship_name):
            break
        # if no role in given relationship, default to "this/<relationship_name>"
        return target_instance or RoleInstanceID(self.profile.name, relationship_name)
