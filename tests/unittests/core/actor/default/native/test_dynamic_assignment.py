""" Dynamic role assignment without using the native role. Contained for comparison. """
import unittest
from threading import Thread

from roleml.core.actor.group.impl.null import CollectiveImplementorDisabled
from roleml.core.context import ActorProfile, Context, RoleInstanceID
from roleml.core.messaging.null import ProcedureInvokerDisabled, ProcedureProviderDisabled
from roleml.core.role.elements import ElementImplementation
from roleml.core.role.exceptions import CallerError
from roleml.core.role.types import Message
from tests.fixtures.actors.basic import TestActor
from tests.fixtures.roles.features.dynamic import FigureBuyer, FigureShop, Warehouse


class RoleDynamicAssignmentTestCase(unittest.TestCase):

    def setUp(self) -> None:
        self.value = None

        profile = ActorProfile('User1', '127.0.0.1')
        context = Context.build(profile)
        self.actor = TestActor(
            profile, context=context,
            procedure_invoker=ProcedureInvokerDisabled(profile.name, profile.address, context.contacts),
            procedure_provider=ProcedureProviderDisabled(profile.name, profile.address, context.contacts),
            collective_implementor=CollectiveImplementorDisabled())

    def test_dynamic_assign(self):
        actor = self.actor

        buyer = FigureBuyer(money=20000)
        actor.add_role('buyer', buyer)
        Thread(target=actor.run).start()

        # add another role while the actor is running (and adjust relationships)
        shop = FigureShop(price=1500)
        actor.add_role('shop', shop)
        actor.start_role('shop')
        actor.ctx.relationships.add_to_relationship('shop', RoleInstanceID('User1', 'shop'))

        self.assertEqual(buyer.buy(), 'figure')
        self.assertEqual(buyer.balance, 20000 - 1500)

    def test_dynamic_remove(self):
        actor = self.actor

        shop = FigureShop(price=1500)
        actor.add_role('shop', shop)
        actor.ctx.relationships.add_to_relationship('shop', RoleInstanceID('User1', 'shop'))
        Thread(target=actor.run).start()

        # terminate the role
        actor.ctx.relationships.remove_from_relationship('shop', RoleInstanceID('User1', 'shop'))
        actor.role_status_manager.ctrl('shop').terminate(force=True)    # managers will do their things

        with self.assertRaises(RuntimeError):
            _ = actor.role_status_manager.ctrl('shop')
        self.assertEqual(len(list(actor.ctx.relationships.get_relationship('shop'))), 0)
        with self.assertRaises(CallerError):
            actor.call('foo', RoleInstanceID('User1', 'shop'), 'price', Message())

    def test_simple_recovery(self):
        a1 = self.actor

        shop = FigureShop(price=1500)
        a1.add_role('shop', shop)
        a1.implement_element('shop', 'warehouse',
                             ElementImplementation(destructor=self._save_value, constructor_args={'stock': 20}))
        Thread(target=a1.run).start()

        p2 = ActorProfile('Li', '127.0.0.1')
        context = Context.build(p2)
        a2 = TestActor(
            p2, context=context,
            procedure_invoker=ProcedureInvokerDisabled(p2.name, p2.address, context.contacts),
            procedure_provider=ProcedureProviderDisabled(p2.name, p2.address, context.contacts),
            collective_implementor=CollectiveImplementorDisabled())
        Thread(target=a2.run).start()

        # first terminate the role in a1
        self.assertEqual(shop.stock, 20)
        a1.stop_role('shop')
        self.assertEqual(self.value, 20)

        # then start it in a2, restoring the state
        new_shop = FigureShop(price=1000)
        a2.add_role('shop', new_shop)
        a2.implement_element('shop', 'warehouse', ElementImplementation(constructor=self._load_value_maker(Warehouse)))

        # check
        self.assertEqual(new_shop.stock, 20)

    def _save_value(self, obj):
        self.value = obj.value

    def _load_value_maker(self, cls: type):
        return lambda: cls(self.value)


if __name__ == '__main__':
    unittest.main()
