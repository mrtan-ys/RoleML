from typing import Optional

from roleml.core.actor.default.managers.runnable import RunnableManager
from roleml.core.actor.group.base import CollectiveImplementor
from roleml.core.builders.actor import BaseActorBuilder
from roleml.core.context import ActorProfile, Context
from roleml.core.messaging.base import ProcedureInvoker, ProcedureProvider
from roleml.core.role.base import Role
from tests.fixtures.actors.template import ActorTemplate


class TestActor(ActorTemplate):

    def __init__(self, profile: ActorProfile, *, context: Optional[Context] = None,
                 procedure_invoker: ProcedureInvoker, procedure_provider: ProcedureProvider,
                 collective_implementor: CollectiveImplementor,
                 handshakes: Optional[list[str]] = None):
        super().__init__(profile, context=context,
                         procedure_invoker=procedure_invoker, procedure_provider=procedure_provider,
                         collective_implementor=collective_implementor, handshakes=handshakes)

        init_args = (self.ctx, self.thread_manager, self.role_status_manager, procedure_invoker, procedure_provider)
        self.runnable_manager = RunnableManager(*init_args)     # stop Runnable first when terminating

        self.roles: dict[str, Role] = {}

    def _add_role_to_managers(self, role: Role):
        super()._add_role_to_managers(role)
        self.runnable_manager.add_role(role)
        self.roles[role.name] = role


class TestActorBuilder(BaseActorBuilder[TestActor]):

    def _create_actor(self, ctx: Context, handshakes: Optional[list[str]]) -> TestActor:
        return TestActor(
            self.profile, context=ctx,
            procedure_invoker=self.artifacts.procedure_invoker, procedure_provider=self.artifacts.procedure_provider,
            collective_implementor=self.artifacts.collective_implementor, handshakes=handshakes)
