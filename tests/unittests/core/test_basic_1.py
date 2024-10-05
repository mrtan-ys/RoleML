import json
import unittest
from pathlib import Path
from threading import Thread

from roleml.core.actor.group.impl.null import CollectiveImplementorDisabled
from roleml.core.context import ActorProfile, RoleInstanceID, Context
from roleml.core.role.base import Role
from roleml.core.messaging.null import ProcedureInvokerDisabled, ProcedureProviderDisabled
from tests.fixtures.actors.basic import TestActorBuilder, TestActor
from tests.fixtures.roles.basic import Host, Guest


class RoleMLHelloworldTestCase(unittest.TestCase):

    # created threads are not manually joined for simplicity

    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture_root = Path(__file__).parent.parent.parent / 'fixtures'

    def test_raw_code_creation(self):
        profile = ActorProfile('User1', '127.0.0.1')
        context = Context.build(profile)
        actor = TestActor(profile, context=context,
                          procedure_invoker=ProcedureInvokerDisabled(profile.name, profile.address, context.contacts),
                          procedure_provider=ProcedureProviderDisabled(profile.name, profile.address, context.contacts),
                          collective_implementor=CollectiveImplementorDisabled())
        actor.add_role('jerry', Host())
        actor.start_role('jerry')
        guest = Guest(method='offline', purpose='have lunch')
        actor.add_role('tom', guest)
        actor.start_role('tom')
        actor.ctx.relationships.add_to_relationship('host', RoleInstanceID('User1', 'jerry'))
        result = guest.do_visit()
        self.assertEqual(f'Hello, User1! This is User1. Feel free to have lunch here.', result)

    def test_call_handler_1(self):
        builder = TestActorBuilder()
        with open(self.fixture_root / 'configs' / 'basic_host_guest.json') as f:
            builder.load_config(json.load(f))
        actor = builder.build()
        t = Thread(target=actor.run)
        t.start()
        t.join()    # it's OK because we are not running a native role in the test actor
        tom: Role = actor.roles['tom']
        self.assertIsInstance(tom, Guest)
        result = tom.do_visit()
        self.assertEqual(result, f'Hello, Test! This is Test. Feel free to have lunch here.')

    def test_call_handler_2(self):
        builder = TestActorBuilder()
        with open(self.fixture_root / 'configs' / 'basic_host_guest.json') as f:
            builder.load_config(json.load(f))
        builder.roles['tom'].config.options['method'] = 'online'
        actor = builder.build()
        t = Thread(target=actor.run)
        t.start()
        t.join()    # it's OK because we are not running a native role in the test actor
        tom = actor.roles['tom']
        self.assertIsInstance(tom, Guest)
        result = tom.do_visit()
        self.assertEqual(result, f'Hello, Test! This is Test. Feel free to have lunch here.')


if __name__ == '__main__':
    unittest.main()
