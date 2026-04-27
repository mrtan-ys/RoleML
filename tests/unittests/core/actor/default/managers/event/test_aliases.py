import time
import unittest

from roleml.core.context import RoleInstanceID
from tests.fixtures.roles.features.aliases import PopUpShop, Accountant
from tests.unittests.core.actor.default.managers.base import DefaultActorManagersTestCase


class EventChannelAliasesTestCase(DefaultActorManagersTestCase):

    def test_event_channel_alias(self):
        pop_up_shop = PopUpShop(10)
        self.actorB.add_role('pop-up-shop', pop_up_shop)
        self.actorB.start_role('pop-up-shop')
        accountant = Accountant()
        self.actorA.add_role('accountant', accountant)
        self.actorA.start_role('accountant')
        self.actorA.ctx.relationships.add_to_relationship(
            'pop-up-shop', RoleInstanceID(self.profileB.name, 'pop-up-shop'))
        time.sleep(2)
        for _ in range(10):
            pop_up_shop.purchase()
        self.assertTrue(accountant.time_to_review)


if __name__ == '__main__':
    unittest.main()
