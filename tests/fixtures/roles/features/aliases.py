from roleml.core.context import RoleInstanceID
from roleml.core.role.base import Role
from roleml.core.role.channels import Alias, Task


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
