from roleml.library.workload.util.arithmetic.base import BasicArithmeticOps


class DefaultBasicArithmeticOps(BasicArithmeticOps):

    def add(self, a, b): return a + b

    def minus(self, a, b): return a - b

    def multiply(self, a, multiplier: int | float): return a * multiplier

    def divide(self, a, divider: int | float): return a / divider
