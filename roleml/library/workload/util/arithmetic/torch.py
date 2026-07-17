from typing import Any

from roleml.library.workload.util.arithmetic.base import BasicArithmeticOps


def state_dict_add(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    return {k: (a[k] + b[k]) for k in a}


def state_dict_minus(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    return {k: (a[k] - b[k]) for k in a}


def state_dict_multiply(a: dict[str, Any], multiplier: int | float) -> dict[str, Any]:
    return {k: (a[k] * float(multiplier)) for k in a}


def state_dict_divide(a: dict[str, Any], divider: int | float) -> dict[str, Any]:
    return {k: (a[k] / float(divider)) for k in a}


class TorchStateDictArithmeticOps(BasicArithmeticOps[dict[str, Any]]):

    def add(self, a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
        return state_dict_add(a, b)

    def minus(self, a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
        return state_dict_minus(a, b)

    def multiply(self, a: dict[str, Any], multiplier: int | float) -> dict[str, Any]:
        return state_dict_multiply(a, multiplier)

    def divide(self, a: dict[str, Any], divider: int | float) -> dict[str, Any]:
        return state_dict_divide(a, divider)
