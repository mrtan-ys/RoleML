import unittest
from typing import Generic
from abc import abstractmethod

from roleml.core.actor.group.impl.null import CollectiveImplementorDisabled
from roleml.core.builders.helpers import ActorType
from roleml.core.context import ActorProfile, Context
from roleml.core.messaging.null import ProcedureInvokerDisabled, ProcedureProviderDisabled


class SingleActorTestCase(unittest.TestCase, Generic[ActorType]):

    @property
    @abstractmethod
    def actor_class(self) -> type[ActorType]: ...

    def setUp(self):
        profile = ActorProfile('User1', '127.0.0.1')
        context = Context.build(profile)
        self.actor: ActorType = self.actor_class(
            profile, context=context,
            procedure_invoker=ProcedureInvokerDisabled(profile.name, profile.address, context.contacts),
            procedure_provider=ProcedureProviderDisabled(profile.name, profile.address, context.contacts),
            collective_implementor=CollectiveImplementorDisabled())


if __name__ == '__main__':
    unittest.main()
