from roleml.core.role.base import Role
from roleml.core.role.channels import Event, Service


class EventProvider(Role):

    visited = Event()

    @Service
    def visit(self, *_, **__):
        self.visited.emit({'info': 'Event triggered!', 'a': 1, 'b': 2, 'c': 3})
