from abc import ABC, abstractmethod
from typing import Iterable, Optional

from roleml.core.context import Context, RoleInstanceID

__all__ = ['ActorGroup', 'Relationship', 'RoleInstances']


class ActorGroup(ABC):

    @property
    @abstractmethod
    def targets(self) -> Iterable[RoleInstanceID]: ...


class Relationship(ActorGroup):

    def __init__(self, name: str, context: Optional[Context] = None):
        self.name = name
        ctx = context or Context.active_context()
        self.relationships = ctx.relationships

    @property
    def targets(self) -> Iterable[RoleInstanceID]:
        return self.relationships.get_relationship_view(self.name)


class RoleInstances(ActorGroup):

    def __init__(self, instances: Iterable[tuple[str, str]]):   # compatible with RoleInstanceID
        self.instances = set(RoleInstanceID(*item) for item in instances)

    @property
    def targets(self) -> Iterable[RoleInstanceID]:
        return self.instances
