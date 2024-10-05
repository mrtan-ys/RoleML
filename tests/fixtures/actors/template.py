from typing import Optional

from roleml.core.actor.base import BaseActor
from roleml.core.actor.default.managers.element import ElementManager
from roleml.core.actor.default.managers.event import EventManager
from roleml.core.actor.default.managers.service import ServiceManager
from roleml.core.actor.default.managers.task import TaskManager
from roleml.core.actor.group.base import CollectiveImplementor
from roleml.core.context import ActorProfile, Context
from roleml.core.messaging.base import ProcedureInvoker, ProcedureProvider

# omitting __all__ here so that subclasses can use import * to replace multiple lines of import


class ActorTemplate(BaseActor):

    def __init__(self, profile: ActorProfile, *, context: Optional[Context] = None,
                 procedure_invoker: ProcedureInvoker, procedure_provider: ProcedureProvider,
                 collective_implementor: CollectiveImplementor,
                 handshakes: Optional[list[str]] = None):
        super().__init__(profile, context=context,
                         procedure_invoker=procedure_invoker, procedure_provider=procedure_provider,
                         collective_implementor=collective_implementor, handshakes=handshakes)

        init_args = (self.ctx, self.thread_manager, self.role_status_manager, procedure_invoker, procedure_provider)
        self.service_manager = ServiceManager(*init_args)
        self.task_manager = TaskManager(*init_args)
        self.event_manager = EventManager(*init_args)
        self.element_manager = ElementManager(*init_args)


def make_simple_actor(actor_cls: type[ActorTemplate], profile: ActorProfile = ActorProfile('User1', '127.0.0.1')):
    from roleml.core.messaging.null import ProcedureInvokerDisabled
    from roleml.core.messaging.null import ProcedureProviderDisabled
    from roleml.core.actor.group.impl.null import CollectiveImplementorDisabled
    context = Context.build(profile)
    actor = actor_cls(profile, context=context,
                      procedure_invoker=ProcedureInvokerDisabled(profile.name, profile.address, context.contacts),
                      procedure_provider=ProcedureProviderDisabled(profile.name, profile.address, context.contacts),
                      collective_implementor=CollectiveImplementorDisabled())
    return actor
