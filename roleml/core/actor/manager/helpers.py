import operator
from typing import Any, Callable, Iterable, Mapping, Optional

from roleml.core.role.types import Args

__all__ = ['EventConditionChecker', 'check_conditions', 'parse_condition', 'parse_conditions']


EventConditionChecker = Callable[[Args], bool]


def check_conditions(properties: Args, conditions: Iterable[EventConditionChecker]) -> bool:
    if not properties or not conditions:
        return True
    for op in conditions:
        if not op(properties):
            return False
    return True


__COMMON_OPS = {
    None: operator.eq,
    '': operator.eq,
    'eq': operator.eq,
    'gt': operator.gt,
    'ge': operator.ge,
    'lt': operator.lt,
    'le': operator.le,
    '==': operator.eq,
    '>': operator.gt,
    '>=': operator.ge,
    '<': operator.lt,
    '<=': operator.le,
    'contains': operator.contains,
}


def parse_condition(key: str, value) -> EventConditionChecker:
    key_processed = key.split('__')
    name, op = key_processed if len(key_processed) == 2 else (key_processed[0], None)
    op_func = __COMMON_OPS.get(op)
    if op_func:
        def condition_checker(properties: Args) -> bool:
            if name not in properties:
                return False
            ev_value = properties[name]
            try:
                return op_func(ev_value, value)
            except Exception:   # noqa
                return False
        return condition_checker
    else:
        raise ValueError(f'operator {key} not supported')


__parsed_conditions_cache: dict[int, list[EventConditionChecker]] = {}


def parse_conditions(conditions: Optional[Mapping[str, Any]]) -> Iterable[EventConditionChecker]:
    if not conditions:
        return []
    if (id(conditions)) in __parsed_conditions_cache:
        return __parsed_conditions_cache[id(conditions)]
    else:
        parsed_conditions = [parse_condition(key, value) for key, value in conditions.items()]
        __parsed_conditions_cache[id(conditions)] = parsed_conditions
        return parsed_conditions
