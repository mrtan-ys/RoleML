from typing import Iterable, Any

from roleml.core.context import RoleInstanceID
from roleml.core.role.base import Role
from roleml.core.role.channels import Service


class ClientConfigurator(Role):

    def __init__(self, num_epochs: int = 1):
        super().__init__()
        self.num_epochs = num_epochs

    @Service(expand=True)
    def configure(self, _, clients: Iterable[RoleInstanceID]) -> dict[RoleInstanceID, dict[str, Any]]:
        return {client: {'num_epochs': self.num_epochs} for client in clients}
