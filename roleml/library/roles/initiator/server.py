from typing import Optional

from roleml.core.context import RoleInstanceID
from roleml.core.messaging.types import MyArgs
from roleml.core.role.base import Role
from roleml.core.role.channels import Service
from roleml.shared.interfaces import Runnable
from roleml.shared.multithreading.util.limiters import CallAtMostOnceLimiter
from roleml.shared.multithreading.util.timers import TimerLocal


class ServerInitiator(Role, Runnable):

    def __init__(self, min_clients: int = 10, max_seconds: int = 86400, relationship_name: str = 'trainer'):
        super().__init__()
        self.min_clients = min_clients
        self.max_seconds = max_seconds
        self.relationship_name = relationship_name
        self.cumulated_clients = 0
        self.start_timer = TimerLocal()
        self.start_at_most_once = CallAtMostOnceLimiter(self.start_impl)

    @Service(expand=True)
    def register(self, caller: RoleInstanceID, instance_name: Optional[str] = None):
        self.logger.info(f'welcome {caller.actor_name}')
        new_instance = RoleInstanceID(caller.actor_name, instance_name or caller.instance_name)
        self.register_impl(new_instance)
        self.call('/', 'update-relationship',
                  MyArgs(relationship_name=self.relationship_name, op='add', instances=[new_instance]))
        self.cumulated_clients += 1
        if self.cumulated_clients >= self.min_clients:
            self.start_at_most_once()

    def run(self):
        # important: do not directly sleep for a long time since it will prevent an actor from exiting
        self.start_timer.wait(self.max_seconds, on_timeout=self.start_at_most_once)

    def stop(self):
        self.start_timer.interrupt()
    
    def register_impl(self, instance: RoleInstanceID):
        # may be overridden
        pass

    def start_impl(self):
        # should be overridden
        pass
