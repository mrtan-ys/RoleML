import unittest

from roleml.core.context import RoleInstanceID
from tests.fixtures.roles.features.aliases import Customer, Restaurant
from tests.unittests.core.actor.default.managers.base import DefaultActorManagersTestCase


class TaskChannelAliasesTestCase(DefaultActorManagersTestCase):

    def test_task_channel_alias(self):
        self.actorB.add_role('restaurant', Restaurant())
        self.actorB.start_role('restaurant')
        customer = Customer()
        self.actorA.add_role('customer', customer)
        self.actorA.start_role('customer')
        r1 = customer.order_method_a(RoleInstanceID(self.profileB.name, 'restaurant'))
        r2 = customer.order_method_b(RoleInstanceID(self.profileB.name, 'restaurant'))
        self.assertEqual(r1, r2)


if __name__ == '__main__':
    unittest.main()
