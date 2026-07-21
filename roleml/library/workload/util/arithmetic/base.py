from typing import Protocol

from roleml.shared.types import Value


class BasicArithmeticOps(Protocol[Value]):

    def add(self, a: Value, b: Value) -> Value: ...

    def minus(self, a: Value, b: Value) -> Value: ...

    def multiply(self, a: Value, multiplier: int | float) -> Value: ...

    def divide(self, a: Value, divider: int | float) -> Value: ...
