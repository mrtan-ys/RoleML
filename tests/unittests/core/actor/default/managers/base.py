import unittest
from threading import Thread
from typing import ClassVar

from roleml.core.actor.group.impl.sequential import SequentialCollectiveImplementor
from roleml.core.context import ActorProfile, Context
from roleml.extensions.messaging.default.separate import DefaultProcedureInvoker, DefaultProcedureProvider
from tests.fixtures.actors.basic import TestActor


class DefaultActorManagersTestCase(unittest.TestCase):

    profileA: ClassVar[ActorProfile]
    profileB: ClassVar[ActorProfile]

    actorA: TestActor
    actorB: TestActor

    @classmethod
    def setUpClass(cls) -> None:
        cls.profileA = ActorProfile('A', '127.0.0.1:5000')
        cls.profileB = ActorProfile('B', '127.0.0.1:5001')

    def setUp(self) -> None:
        contextA = Context.build(self.profileA)     # noqa: variable naming
        contextA.contacts.add_contact(self.profileB)
        self.actorA = TestActor(
            self.profileA, context=contextA,
            procedure_invoker=DefaultProcedureInvoker(self.profileA.name, self.profileA.address, contextA.contacts),
            procedure_provider=DefaultProcedureProvider(self.profileA.name, self.profileA.address, contextA.contacts),
            collective_implementor=SequentialCollectiveImplementor())
        Thread(target=self.actorA.run).start()
        contextB = Context.build(self.profileB)     # noqa: variable naming
        contextB.contacts.add_contact(self.profileA)
        self.actorB = TestActor(
            self.profileB, context=contextB,
            procedure_invoker=DefaultProcedureInvoker(self.profileB.name, self.profileA.address, contextB.contacts),
            procedure_provider=DefaultProcedureProvider(self.profileB.name, self.profileB.address, contextB.contacts),
            collective_implementor=SequentialCollectiveImplementor())
        Thread(target=self.actorB.run).start()

    def tearDown(self) -> None:
        self.actorA.stop()
        self.actorB.stop()


if __name__ == '__main__':
    unittest.main()
