from typing import TypeVar

from roleml.core.actor.base import BaseActor
from roleml.core.role.base import Role


ActorType = TypeVar('ActorType', bound=BaseActor)
RoleType = TypeVar('RoleType', bound=Role)
