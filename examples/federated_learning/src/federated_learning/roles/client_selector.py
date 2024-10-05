import random
from typing import Optional

from roleml.core.context import RoleInstanceID
from roleml.core.role.base import Role
from roleml.core.role.channels import Service
from roleml.core.role.exceptions import CallerError


class ClientSelector(Role):

    RELATIONSHIP_NAME = 'client'

    @Service(expand=True)
    def select_client(self, _, ratio: Optional[float] = None, count: Optional[int] = None) -> list[RoleInstanceID]:
        with self.ctx.relationships:
            # lock the current state of relationships
            candidates = self.ctx.relationships.get_relationship_unsafe(self.RELATIONSHIP_NAME)
            k = int(len(candidates) * ratio) if ratio else (count or 1)
            if k == len(candidates):
                return list(candidates)
            if 0 < k < len(candidates):
                return random.sample(list(candidates), k)
            # the following is mainly for user input checks
            raise CallerError(
                f'invalid number of clients to select (allowed 1-{len(candidates)}, got {k} from {ratio=} & {count=})')
