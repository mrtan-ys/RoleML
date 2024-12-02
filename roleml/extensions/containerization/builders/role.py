from typing_extensions import override
from roleml.core.builders.role import RoleBuilder, RoleSpec
from roleml.extensions.containerization.controller.role import ContainerizedRole


__all__ = ['ContainerizedRoleBuilder']


class ContainerizedRoleBuilder(RoleBuilder):
    
    def __init__(self, name: str, spec: str | RoleSpec):
        super().__init__(name, spec)

    @override
    def build(self) -> None:
        self.role = ContainerizedRole(self.config)
