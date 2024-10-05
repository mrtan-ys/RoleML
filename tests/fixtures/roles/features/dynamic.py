from typing import Optional

from roleml.core.context import RoleInstanceID
from roleml.core.role.base import Role
from roleml.core.role.channels import Service
from roleml.core.role.elements import Element


class Warehouse:

    def __init__(self, stock: int = 10):
        self.stock = stock

    def take(self):
        if self.stock == 0:
            raise ValueError('Out of stock!')
        else:
            self.stock -= 1

    @property
    def value(self):
        return self.stock


class FigureShop(Role):

    def __init__(self, price: int = 1000):
        super().__init__()
        self._price = price

    warehouse = Element(Warehouse, default_constructor=Warehouse)

    @Service(expand=True)
    def purchase(self, _, money: int):
        if money < self._price:
            raise ValueError('Money not enough!')
        self.warehouse().take()
        return True

    @Service(expand=True)
    def price(self, _):
        return self._price

    @property
    def stock(self):
        return self.warehouse().stock


class FigureBuyer(Role):

    def __init__(self, money: int = 10000):
        super().__init__()
        self._balance = money

    def buy(self) -> str:
        price: int = self.call('shop', 'price')
        if self._balance >= price:
            self._balance -= price
            self.call('shop', 'purchase', args={'money': price})
        return 'figure'

    @property
    def balance(self) -> int:
        return self._balance


class TemporaryStore:

    def __init__(self):
        self.stock = 0

    def store(self, value: int):
        self.stock += value

    def fetch(self, value: Optional[int] = None) -> int:
        if value is None:
            value = self.stock
        if value > self.stock:
            raise ValueError('Stored items are fewer than requested')
        self.stock -= value
        return value

    @property
    def value(self):
        return self.stock


class Manufacturer(Role):

    store = Element(TemporaryStore, default_constructor=TemporaryStore)

    def assign_shop(self, actor_name: str, instance_name: str, value: Optional[int] = None):
        target = RoleInstanceID(actor_name, 'actor')
        real_value = self.store().fetch(value)
        self.call_task(target, 'assign-role', args={
            'name': instance_name,
            'spec': {
                'class': 'tests.fixtures.roles.features.dynamic.FigureShop',
                'impl': {
                    'warehouse': {
                        'class': 'tests.fixtures.roles.features.dynamic.Warehouse',
                        'constructor_args': {'stock': real_value}
                    }
                }
            }
        }).result()
        self.call('/', 'update-relationship', args={
            'relationship_name': 'shop', 'op': 'add', 'instances': [RoleInstanceID(actor_name, instance_name)]
        })

    def remove_shop(self, actor_name: str, instance_name: str):
        target = RoleInstanceID(actor_name, 'actor')
        self.call_task(target, 'terminate-role', args={'name': instance_name}).result()
        self.call('/', 'update-relationship', args={
            'relationship_name': 'shop', 'op': 'remove', 'instances': [RoleInstanceID(actor_name, instance_name)]
        })
