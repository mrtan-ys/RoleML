import unittest
from threading import Thread

from roleml.core.context import RoleInstanceID
from tests.fixtures.actors.template import make_simple_actor
from tests.fixtures.roles.plugins.partner import RacingDriver, RaceEngineer
from tests.unittests.extensions.plugins.partner.actor import TestPartnerActor


class PartnerUseTestCase(unittest.TestCase):

    def setUp(self) -> None:
        self.actor = make_simple_actor(TestPartnerActor)

    def test_partner_use(self):
        actor = self.actor
        actor.add_role('race-driver', RacingDriver())
        racing_engineer = RaceEngineer()
        actor.add_role('race-engineer', racing_engineer)
        actor.ctx.relationships.add_to_relationship('driver', RoleInstanceID(actor.profile.name, 'race-driver'))
        t = Thread(target=actor.run)
        t.start()
        t.join()
        racing_engineer.race_week()
        self.assertTrue(racing_engineer.won)


if __name__ == '__main__':
    unittest.main()
