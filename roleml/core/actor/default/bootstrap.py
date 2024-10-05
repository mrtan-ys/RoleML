from typing import Optional

from roleml.core.actor.default import Actor
from roleml.core.builders.actor import BaseActorBuilder
from roleml.core.context import Context, RoleInstanceID

__all__ = ['ActorBuilder']


class ActorBuilder(BaseActorBuilder[Actor]):

    def _create_actor(self, ctx: Context, handshakes: Optional[list[str]]) -> Actor:
        return Actor(
            self.profile, context=ctx,
            procedure_invoker=self.artifacts.procedure_invoker, procedure_provider=self.artifacts.procedure_provider,
            collective_implementor=self.artifacts.collective_implementor, handshakes=handshakes)

    def _parse_instance_name(self, instance_name: str, default_name: str) -> RoleInstanceID:
        if instance_name[0] == '/':
            return RoleInstanceID(default_name, instance_name[1:])
        li = instance_name.rsplit('/', maxsplit=2)
        # add support for native role
        return RoleInstanceID(li[0], li[1]) if len(li) == 2 else RoleInstanceID(li[0], 'actor')
    