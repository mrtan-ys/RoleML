import time
from typing import TYPE_CHECKING

from roleml.core.builders.role import RoleSpec
from roleml.core.context import RoleInstanceID, ActorProfile
from roleml.core.role.base import Role
from roleml.core.role.channels import Service, Event, Task
from roleml.core.role.exceptions import CallerError
from roleml.core.role.helpers import require_relationship
from roleml.core.status import Status
from roleml.shared.aop import InvocationActivity, after, aspect
from roleml.shared.interfaces import Runnable
from roleml.extensions.containerization.builders.role import ContainerizedRoleBuilder

if TYPE_CHECKING:
    from roleml.extensions.containerization.runtime.impl import RoleRuntime


class NativeRole(Role, Runnable):

    def __init__(self):
        super().__init__()
        self._should_stop = False
        self.base: RoleRuntime  # type hinting

    heartbeat = Event()

    def run(self):
        aspect(after(target=self.ctx.contacts, method='add_contact')(self._advice_after_add_contact))
        aspect(
            after(target=self.ctx.relationships, method='add_to_relationship')(self._advice_after_add_to_relationship)
        )
        aspect(
            after(target=self.ctx.relationships, method='remove_from_relationship')
            (self._advice_after_remove_from_relationship)
        )
        while not self._should_stop:
            self.heartbeat.emit()
            try:
                time.sleep(20)  # TODO configurable timeout interval
            except KeyboardInterrupt:
                raise

    def stop(self):
        self._should_stop = True

    contact_updated = Event()

    @require_relationship('manager', 'contacts can only be updated by manager')
    @Service('update-contacts', expand=True)
    def update_contacts(self, _, contacts: dict[str, str]):
        for actor_name, address in contacts.items():
            self.ctx.contacts.add_contact(ActorProfile(actor_name, address))
            # see below for callback

    def _advice_after_add_contact(self, activity: InvocationActivity, _):
        actor_name = activity.args[0].name
        self.logger.info(f'contact updated for actor {actor_name}')
        self.contact_updated.emit(args={'name': actor_name})
    
    handshake_completed = Event()

    @require_relationship('manager', 'handshake with other actors can only be initiated by manager')
    @Service
    def handshake(self, _, name: str):
        self.base.handshake(name)
        self.handshake_completed.emit(args={'name': name})
    
    handwave_completed = Event()

    @require_relationship('manager', 'handwave with other actors can only be initiated by manager')
    @Service
    def handwave(self, _, name: str):
        self.base.handwave(name)
        self.handwave_completed.emit(args={'name': name})

    relationship_updated = Event()

    @require_relationship('manager', 'relationships can only be updated by manager')
    @Service('update-relationship', expand=True)
    def update_relationship(self, _, relationship_name: str, op: str, instances: list[RoleInstanceID]):
        if op == 'add':
            self.ctx.relationships.add_to_relationship(relationship_name, *instances)
        elif op == 'remove':
            self.ctx.relationships.remove_from_relationship(relationship_name, *instances)
        else:
            raise CallerError(f'invalid relationship op {op}')
        # see below for callbacks

    def _advice_after_add_to_relationship(self, activity: InvocationActivity, _):
        relationship_name: str = activity.args[0]
        instances: list[RoleInstanceID] = list(activity.args[1:])
        self.logger.info(f'{len(instances)} role instances added to relationship {relationship_name}')
        self.relationship_updated.emit(args={'name': relationship_name, 'op': 'add', 'instances': instances})

    def _advice_after_remove_from_relationship(self, activity: InvocationActivity, _):
        relationship_name: str = activity.args[0]
        instances: list[RoleInstanceID] = list(activity.args[1:])
        self.logger.info(f'{len(instances)} role instances removed from relationship {relationship_name}')
        self.relationship_updated.emit(args={'name': relationship_name, 'op': 'remove', 'instances': instances})

    @require_relationship('manager', 'relationship links can only be updated by manager')
    @Service('add-relationship-link', expand=True)
    def add_relationship_link(self, _, from_relationship_name: str, to_relationship_name: str):
        with self.ctx.relationships:
            try:
                self.ctx.relationships.link_relationship(from_relationship_name, to_relationship_name)
            except ValueError as e:
                raise CallerError(str(e))
            else:
                instances = list(self.ctx.relationships.get_relationship(from_relationship_name))
        self.logger.info(f'relationship link added ({from_relationship_name} -> {to_relationship_name})')
        self.relationship_updated.emit(args={'name': from_relationship_name, 'op': 'add', 'instances': instances})

    role_assigned = Event()

    @require_relationship('manager', 'roles can only be deployed by manager')
    @Task('assign-role', expand=True)
    def assign_role(self, _, name: str, spec: RoleSpec):
        role_builder = ContainerizedRoleBuilder(name, spec)
        role_builder.build()
        role_builder.install(self.base, start=True)
        self.logger.info(f'role instance {name} assigned via native role')
        self.role_assigned.emit(args={'name': name, 'cls': role_builder.role.__class__.__name__})

    role_removed = Event()

    @require_relationship('manager', 'roles can only be terminated by manager')
    @Task('terminate-role', expand=True)
    def terminate_role(self, _, name: str):
        self.base.stop_role(name)   # managers will do their things
        self.logger.info(f'role instance {name} removed via native role')
        self.role_removed.emit(args={'name': name})

    # TODO below necessary? or implement in Actor and expose API here?

    role_status_changed = Event()

    @require_relationship('manager', 'role status can only be changed by manager')
    @Task('change-role-status', expand=True)
    def change_role_status(self, _, name: str, status: Status):
        status = Status(status)     # allow status to be specified as a str
        if status == Status.TERMINATED:
            raise CallerError('please use terminate-role for role termination')
        self.logger.info(f'role status change attempt to {name} via native role')
        with self.base.management_lock:
            try:
                ctrl = self.base.role_status_manager.ctrl(name)
            except RuntimeError as e:
                raise CallerError(f'role named {name} not found') from e
            else:
                ctrl.status = status
                self.role_status_changed.emit(args={'name': name, 'new_status': status})

    @require_relationship('manager', 'role status can only be obtained by manager')
    @Service('get-role-status', expand=True)
    def get_role_status(self, _, name: str) -> Status:
        with self.base.management_lock:
            try:
                ctrl = self.base.role_status_manager.ctrl(name)
            except RuntimeError as e:
                raise CallerError(f'role named {name} not found') from e
            else:
                return ctrl.status

    @Service('change-controller', expand=True)
    def change_controller(self, _, new_profile: ActorProfile, old_profile: ActorProfile):
        self.base.change_controller(new_profile, old_profile)
        self.logger.info(f'controller changed to {new_profile} via native role')
        
    @Service('update-instance-id', expand=True)
    def update_instance_id(self, _, old_instance_id: RoleInstanceID, new_instance_id: RoleInstanceID):
        self.base.update_instance_id(old_instance_id, new_instance_id)
        self.logger.info(f'instance id updated from {old_instance_id} to {new_instance_id} via native role')
