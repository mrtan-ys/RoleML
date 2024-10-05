import unittest
from threading import Thread
from typing import ClassVar

from roleml.core.context import Contacts, ActorProfile
from roleml.extensions.messaging.comb.grpc.component import GRPCMessagingComponent


class GRPCMessagingTestCase(unittest.TestCase):

    profileA: ClassVar[ActorProfile]
    profileB: ClassVar[ActorProfile]

    componentA: GRPCMessagingComponent
    componentB: GRPCMessagingComponent

    @classmethod
    def setUpClass(cls) -> None:
        cls.profileA = ActorProfile('A', '127.0.0.1:5000')
        cls.profileB = ActorProfile('B', '127.0.0.1:5001')

    def setUp(self) -> None:
        self.componentA = GRPCMessagingComponent(self.profileA.name, self.profileA.address, Contacts(self.profileB))
        self.componentB = GRPCMessagingComponent(self.profileB.name, self.profileB.address, Contacts(self.profileA))
        Thread(target=self.componentA.run, daemon=True).start()
        Thread(target=self.componentB.run, daemon=True).start()

    def tearDown(self) -> None:
        self.componentA.stop()
        self.componentB.stop()


if __name__ == '__main__':
    unittest.main()
