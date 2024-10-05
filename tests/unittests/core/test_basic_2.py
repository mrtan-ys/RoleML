import json
import time
import unittest
from pathlib import Path
from threading import Thread

from roleml.core.role.exceptions import HandlerError, CallerError
from tests.fixtures.actors.basic import TestActorBuilder
from tests.fixtures.roles.basic import CarOwner, Car


class RoleMLHelloworld2TestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture_root = Path(__file__).parent.parent.parent / 'fixtures'

    def setUp(self) -> None:
        builder = TestActorBuilder()
        with open(self.fixture_root / 'configs' / 'basic_car.json') as f:
            builder.load_config(json.load(f))
        builder.debug = True
        actor = builder.build()
        t = Thread(target=actor.run)
        t.start()
        t.join()    # it's OK because we are not running a native role in the test actor
        self.actor = actor

    def tearDown(self) -> None:
        self.actor.stop()

    def test_call_exception(self):
        tom = self.actor.roles.get('tom')
        self.assertIsInstance(tom, CarOwner)
        self.assertRaises(HandlerError, tom.do_refund)     # from NotImplementedError

    def test_call_task_return_object(self):
        tom = self.actor.roles.get('tom')
        self.assertIsInstance(tom, CarOwner)
        result = tom.do_buy_car(100000)
        self.assertIsInstance(result, Car)
        self.assertEqual(result.owner, self.actor.profile.name)

    def test_call_task_object_to_object(self):
        tom = self.actor.roles.get('tom')
        self.assertIsInstance(tom, CarOwner)
        tom.do_buy_car(value=100000)
        tom.do_run_car(km=100000)
        self.assertEqual(tom.car.damage, 100)
        car = tom.do_repair_car()
        self.assertIsInstance(car, Car)
        self.assertEqual(car.damage, 0)

    def test_call_task_exception(self):
        tom = self.actor.roles.get('tom')
        self.assertIsInstance(tom, CarOwner)
        self.assertRaises(CallerError, tom.do_buy_car, 10000)

    def test_event(self):
        tom = self.actor.roles.get('tom')
        self.assertIsInstance(tom, CarOwner)
        time.sleep(20)
        self.assertGreater(tom.price_updated, 0)


if __name__ == '__main__':
    unittest.main()
