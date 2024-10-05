import unittest
from threading import Thread
from typing import Optional

from roleml.core.actor.default import Actor
from roleml.core.actor.group.base import CollectiveImplementor
from roleml.core.actor.group.impl.null import CollectiveImplementorDisabled
from roleml.core.context import ActorProfile, Context, RoleInstanceID
from roleml.core.messaging.base import ProcedureInvoker, ProcedureProvider
from roleml.core.role.base import Role
from roleml.core.role.elements import ElementImplementation, ConstructStrategy
from roleml.core.status import Status
from roleml.extensions.messaging.default.separate import DefaultProcedureInvoker, DefaultProcedureProvider
from tests.fixtures.roles.features.dynamic import TemporaryStore, Manufacturer, FigureShop


class RoleDynamicAssignmentTestActor(Actor):

    def __init__(
            self, profile: ActorProfile, *, context: Optional[Context] = None, procedure_invoker: ProcedureInvoker,
            procedure_provider: ProcedureProvider, collective_implementor: CollectiveImplementor,
            handshakes: Optional[list[str]] = None):
        self.roles: dict[str, Role] = {}
        super().__init__(
            profile, context=context, procedure_invoker=procedure_invoker, procedure_provider=procedure_provider,
            collective_implementor=collective_implementor, handshakes=handshakes)

    def add_role(self, instance_name: str, role: Role):
        super().add_role(instance_name, role)
        self.roles[instance_name] = role

    def stop_role(self, instance_name: str):
        super().stop_role(instance_name)
        del self.roles[instance_name]


class RoleDynamicAssignmentDistributedTestCase(unittest.TestCase):

    @staticmethod
    def make_actor(profile: ActorProfile):
        context = Context.build(profile)
        return RoleDynamicAssignmentTestActor(
            profile, context=context,
            procedure_invoker=DefaultProcedureInvoker(profile.name, profile.address, context.contacts),
            procedure_provider=DefaultProcedureProvider(profile.name, profile.address, context.contacts),
            collective_implementor=CollectiveImplementorDisabled())

    def setUp(self) -> None:
        self.temporary_store = TemporaryStore()     # helper object, not a role

        p1 = ActorProfile('Zhang', '127.0.0.1:5501')
        p2 = ActorProfile('Li', '127.0.0.1:5502')
        p3 = ActorProfile('Wang', '127.0.0.1:5503')

        # set up actors (for simplicity, we bypass the builder and construct the actor directly)
        self.a1 = self.make_actor(p1)
        self.manufacturer = Manufacturer()
        self.a1.add_role('manufacturer', self.manufacturer)
        self.a1.implement_element('manufacturer', 'store', ElementImplementation(impl=self.temporary_store))
        for p in (p1, p2, p3):
            self.a1.ctx.contacts.add_contact(p)
        self.a1.ctx.relationships.add_to_relationship('manager', RoleInstanceID('Zhang', 'manufacturer'))
        self.a1.ctx.relationships.add_to_relationship('shop', RoleInstanceID('Li', 'shop'))
        Thread(target=self.a1.run).start()

        self.a2 = self.make_actor(p2)
        self.shop = FigureShop()
        self.a2.add_role('shop', self.shop)
        self.a2.implement_element(
            'shop', 'warehouse',
            ElementImplementation(constructor_args={'stock': 20}, construct_strategy=ConstructStrategy.ONCE_EAGER,
                                  destructor=self._save_value))
        for p in (p1, p2, p3):
            self.a2.ctx.contacts.add_contact(p)
        self.a2.ctx.relationships.add_to_relationship('manager', RoleInstanceID('Zhang', 'manufacturer'))
        Thread(target=self.a2.run).start()

        self.a3 = self.make_actor(p3)
        for p in (p1, p2, p3):
            self.a3.ctx.contacts.add_contact(p)
        self.a3.ctx.relationships.add_to_relationship('manager', RoleInstanceID('Zhang', 'manufacturer'))
        Thread(target=self.a3.run).start()

    def tearDown(self) -> None:
        self.a1.stop()
        self.a2.stop()
        self.a3.stop()

    def _save_value(self, obj):
        self.temporary_store.store(obj.value)

    # region TEST CASES

    def test_dynamic_assign(self):
        self.assertFalse(
            self.a1.ctx.relationships.instance_belongs_to_relationship(RoleInstanceID('Wang', 'shop'), 'shop'))

        self.manufacturer.assign_shop('Wang', 'shop')

        new_shop = self.a3.roles['shop']
        self.assertIsInstance(new_shop, FigureShop)
        self.assertEqual(new_shop.stock, 0)
        self.assertTrue(
            self.a1.ctx.relationships.instance_belongs_to_relationship(RoleInstanceID('Wang', 'shop'), 'shop'))

    def test_dynamic_remove(self):
        self.assertEqual(len(self.a2.roles), 2)     # includes the builtin role
        self.assertTrue(
            self.a1.ctx.relationships.instance_belongs_to_relationship(RoleInstanceID('Li', 'shop'), 'shop'))

        self.manufacturer.remove_shop('Li', 'shop')

        self.assertEqual(len(self.a2.roles), 1)
        self.assertFalse(
            self.a1.ctx.relationships.instance_belongs_to_relationship(RoleInstanceID('Li', 'shop'), 'shop'))

    def test_simple_recovery(self):
        # remove shop in a2, which will save the stock in the destructor
        self.manufacturer.remove_shop('Li', 'shop')
        self.assertEqual(self.temporary_store.value, 20)

        # add shop in a3, using the stock saved
        self.manufacturer.assign_shop('Wang', 'shop')
        self.assertEqual(self.temporary_store.value, 0)

        new_shop = self.a3.roles['shop']
        self.assertIsInstance(new_shop, FigureShop)
        self.assertEqual(new_shop.stock, 20)

    def test_get_role_status(self):
        status = self.manufacturer.call(RoleInstanceID('Li', 'actor'), 'get-role-status', args={'name': 'shop'})
        self.assertEqual(status, Status.READY)

    def test_pause_and_resume_role(self):
        self.assertEqual(self.a2.role_status_manager.ctrl('shop').status, Status.READY)
        self.manufacturer.call_task(RoleInstanceID('Li', 'actor'), 'change-role-status',
                                    args={'name': 'shop', 'status': Status.PAUSED.value}).result()
        self.assertEqual(self.a2.role_status_manager.ctrl('shop').status, Status.PAUSED)
        self.manufacturer.call_task(RoleInstanceID('Li', 'actor'), 'change-role-status',
                                    args={'name': 'shop', 'status': Status.READY.value}).result()
        self.assertEqual(self.a2.role_status_manager.ctrl('shop').status, Status.READY)

    # endregion


if __name__ == '__main__':
    unittest.main()
