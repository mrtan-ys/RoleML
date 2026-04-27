from roleml.core.context import RoleInstanceID
from roleml.core.role.base import Role
from roleml.core.role.channels import Alias, Event, EventHandler, Task


class Restaurant(Role):
    
    @Task(expand=True)
    def beef_rice(self, _) -> str:
        return "beef rice!"

    lunch_a = Alias("beef-rice")


class Customer(Role):

    def order_method_a(self, target: RoleInstanceID) -> str:
        return self.call_task(target, "beef-rice").result()

    def order_method_b(self, target: RoleInstanceID) -> str:
        return self.call_task(target, "lunch-a").result()


class Shop(Role):

    def __init__(self, total_items: int = 10):
        super().__init__()
        self._total_items = total_items

    sold_out = Event()

    def purchase(self):
        if self._total_items > 0:
            self._total_items -= 1
            if self._total_items == 0:
                self.sold_out.emit()
        else:
            raise RuntimeError('sold out!')


class PopUpShop(Shop):

    closed = Alias('sold-out')


class Accountant(Role):

    def __init__(self):
        super().__init__()
        self.time_to_review = False

    @EventHandler('pop-up-shop', 'closed', expand=True)
    def on_pop_up_shop_closed(self, _):
        self.time_to_review = True
