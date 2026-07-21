from collections.abc import Mapping
from math import ceil
from typing import Iterable, Any, Optional

from roleml.core.context import RoleInstanceID
from roleml.core.role.base import Role
from roleml.core.role.channels import Service


class ClientConfigurator(Role):

    def __init__(self, base_epochs_map: Optional[Mapping[str, int]] = None):
        super().__init__()
        self.base_epochs_map = base_epochs_map or {}    # NOTE: for demonstration only, not for actual businesss

    @Service(expand=True)
    def configure(
        self, _, clients: Iterable[RoleInstanceID], annealing_ratio: float = 1.0) -> dict[RoleInstanceID, dict[str, Any]]:
        configurations = {}
        for client in clients:
            base_epochs = self.base_epochs_map.get(client.actor_name, 1)
            actual_epochs = max(1, ceil(base_epochs * annealing_ratio))
            configurations[client] = {'num_epochs': actual_epochs}
        return configurations
