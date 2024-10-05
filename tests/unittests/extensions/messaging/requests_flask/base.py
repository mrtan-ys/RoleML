import unittest
from threading import Thread
from typing import ClassVar

from roleml.core.context import Contacts, ActorProfile
from roleml.extensions.messaging.invokers.requests import RequestsProcedureInvoker
from roleml.extensions.messaging.providers.flask import FlaskProcedureProvider


class RequestsFlaskMessagingTestCase(unittest.TestCase):

    profileA: ClassVar[ActorProfile]
    profileB: ClassVar[ActorProfile]

    invoker: RequestsProcedureInvoker
    provider: FlaskProcedureProvider

    @classmethod
    def setUpClass(cls) -> None:
        cls.profileA = ActorProfile('A', '127.0.0.1:5000')
        cls.profileB = ActorProfile('B', '127.0.0.1:5001')

    def setUp(self) -> None:
        self.invoker = RequestsProcedureInvoker(self.profileA.name, self.profileA.address, Contacts(self.profileB))
        self.provider = FlaskProcedureProvider(self.profileB.name, self.profileB.address, Contacts(self.profileA))
        Thread(target=self.provider.run, daemon=True).start()

    def tearDown(self) -> None:
        self.provider.stop()


if __name__ == '__main__':
    unittest.main()
