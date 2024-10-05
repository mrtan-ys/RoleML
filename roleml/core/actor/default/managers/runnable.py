import logging

from roleml.core.actor.manager.bases import BaseRunnableManager
from roleml.core.role.base import Role
from roleml.core.status import Status
from roleml.shared.interfaces import Runnable


class RunnableManager(BaseRunnableManager):

    runnable_roles: set[str]

    def initialize(self):
        self.runnable_roles = set()
        self.role_status_manager.add_callback(Status.READY, self._on_role_status_ready)
        self.role_status_manager.add_callback(Status.FINALIZING, self._on_role_status_finalizing)
        self.logger = logging.getLogger('roleml.managers.runnable')

    def add_role(self, role: Role):
        if isinstance(role, Runnable):
            assert isinstance(role, Role) and isinstance(role, Runnable)    # to let IDE not complain
            self.runnable_roles.add(role.name)
            self.thread_manager.add_threaded_component(role, name=f'role-{role.name}', start=False)

    def _on_role_status_ready(self, instance_name: str, old_status: Status):
        # this callback is synchronous and when executing, other status transfer of the same role will not happen
        if old_status == Status.STARTING:
            if instance_name in self.runnable_roles:
                self.thread_manager.start_component(f'role-{instance_name}')

    def _on_role_status_finalizing(self, instance_name: str, _):
        if instance_name in self.runnable_roles:
            try:
                self.thread_manager.terminate_component(f'role-{instance_name}')
            except Exception as e:
                self.logger.warning(f'error when terminating role ({instance_name}): {e}')
            self.runnable_roles.remove(instance_name)
