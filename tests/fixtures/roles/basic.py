""" Simple roles for testing purposes. These roles have nothing to do with DML and is only used to verify the
functionalities of the user interfaces. """

import time
from dataclasses import dataclass
from threading import Lock
from typing import Literal, Optional

from roleml.core.context import RoleInstanceID
from roleml.core.messaging.types import Args, Payloads, MyArgs
from roleml.core.role.base import Role
from roleml.core.role.channels import Service, Task, Event, EventHandler
from roleml.core.role.exceptions import CallerError
from roleml.shared.interfaces import Runnable


class Host(Role):

    @Service(expand=True)
    def visit(self, caller: RoleInstanceID, purpose: str):
        return f'Hello, {caller.actor_name}! This is {self.profile.name}. Feel free to {purpose} here.'

    @Service
    def visit_online(self, caller: RoleInstanceID, args: Args, _: Payloads):
        return f'Hello, {caller.actor_name}! This is {self.profile.name}. Feel free to {args["purpose"]} here.'


class Guest(Role):

    def __init__(self, method: Literal['online', 'offline'] = 'offline', *, purpose: str):
        super().__init__()
        self.method = method
        self.purpose = purpose

    def do_visit(self):
        if self.method == 'offline':
            return self.call('host', 'visit', MyArgs(purpose=self.purpose))
        else:
            return self.call('host', 'visit-online', MyArgs(purpose=self.purpose))


@dataclass
class Car:
    owner: str
    damage: int = 0


class CarShop(Role, Runnable):

    def __init__(self, price: int = 100000):
        super().__init__()
        self.lock = Lock()
        self.price = price

    def run(self):
        time.sleep(2)
        for i in range(10):
            time.sleep(1)
            with self.lock:
                self.price += 10000
                self.new_price.emit(MyArgs(price=self.price))

    new_price = Event()

    @Service(expand=True)
    def get_price(self, _) -> int:
        with self.lock:
            return self.price

    @Service(expand=True)
    def refund(self, _, car: Car):
        raise NotImplementedError('We do not support refund')

    @Task(expand=True)
    def buy_car(self, caller: RoleInstanceID, value: int) -> Car:
        with self.lock:
            if value < self.price:
                error_message = f'Insufficient price: {value}'
                # use this if you want also to log the cause
                raise CallerError(error_message) from ValueError(error_message)
        time.sleep(3)   # assuming it takes 3 seconds for the car shop to prepare the car
        return Car(caller.actor_name, 0)

    @Task(expand=True)
    def repair_car(self, _, car: Car) -> Car:   # noqa: static warning
        time.sleep(3)   # assuming it takes 3 seconds for the car shop to fix the car
        car.damage = 0  # unlimited warranty
        return car


class CarOwner(Role):

    def __init__(self):
        super().__init__()
        self.car: Optional[Car] = None
        self.price_updated: int = 0

    @EventHandler('shop', 'new-price')
    def on_new_price(self, _, args: Args, *__):
        self.logger.info(f'New price: {args["price"]}')
        self.price_updated += 1

    def do_buy_car(self, value: int) -> Car:
        self.car = self.call_task('shop', 'buy-car', MyArgs(value=value)).result()  
        return self.car     # type: ignore

    def do_run_car(self, km: int):
        if self.car:
            self.car.damage += km // 1000

    def do_repair_car(self):
        car = self.call_task('shop', 'repair-car', MyArgs(car=self.car)).result()
        return car

    def do_refund(self):
        self.call('shop', 'refund', MyArgs(car=self.car))
