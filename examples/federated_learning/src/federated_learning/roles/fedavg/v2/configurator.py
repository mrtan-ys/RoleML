from collections import defaultdict
from typing import Iterable, Any

from roleml.core.context import RoleInstanceID
from roleml.core.role.base import Role
from roleml.core.role.channels import Service


class ClientConfigurator(Role):

    def __init__(self, selected_rounds_threshold: int = 2, num_epochs_before: int = 2, num_epochs_after: int = 1):
        super().__init__()
        self.selected_rounds_threshold = selected_rounds_threshold
        self.num_epochs_before = num_epochs_before
        self.num_epochs_after = num_epochs_after
        self.selected_rounds_count: defaultdict[RoleInstanceID, int] = defaultdict(int)

    @Service(expand=True)
    def configure(self, _, clients: Iterable[RoleInstanceID]) -> dict[RoleInstanceID, dict[str, Any]]:
        configurations = {}
        for client in clients:
            self.selected_rounds_count[client] += 1
            count = self.selected_rounds_count[client]
            num_epochs = self.num_epochs_before if count <= self.selected_rounds_threshold else self.num_epochs_after
            configurations[client] = {'num_epochs': num_epochs}
        return configurations
