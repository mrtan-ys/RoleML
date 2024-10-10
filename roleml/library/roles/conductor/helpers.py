import random
import re
from itertools import repeat, cycle
from typing import Any, Iterable, Iterator, SupportsIndex

from roleml.shared.types import T


def detect_templates(item, save: dict[tuple, Iterator], path: tuple = ()):
    if isinstance(item, dict):
        for key, value in item.items():
            detect_templates(value, save, path + (key,))
        return save
    elif isinstance(item, list):
        for i, value in enumerate(item):
            detect_templates(value, save, path + (i,))
        return save
    else:
        if _is_template(item):
            save[path] = _build_template_value_producer(item)
        return save


def _is_template(value: Any):
    return bool(re.match('^\\$[race]\\[(.*)]$', str(value)))


class RandomSingleValueProducer:

    def __init__(self, begin: SupportsIndex, end: SupportsIndex, step: SupportsIndex):
        self.begin, self.end, self.step = int(begin), int(end), int(step)

    def __next__(self):
        return random.randrange(self.begin, self.end, self.step)

    def __iter__(self):
        return self


class RandomValueListProducer:

    def __init__(self, begin: SupportsIndex, end: SupportsIndex, step: SupportsIndex, count: SupportsIndex):
        self.range = range(begin, end, step)
        self.count = int(count)

    def __next__(self):
        return random.sample(self.range, k=self.count)

    def __iter__(self):
        return self


def make_random_producer(begin: SupportsIndex, end: SupportsIndex, step: SupportsIndex = 1, count: SupportsIndex = -1):
    count = int(count)
    if count > 0:
        return RandomValueListProducer(begin, int(end) + 1, step, count)
    elif count < 0:
        return RandomSingleValueProducer(begin, int(end) + 1, step)
    else:
        raise ValueError('argument count for random number producer must be non-zero')


def _build_template_value_producer(template: str) -> Iterator:
    assert _is_template(template)
    args = [arg.strip() for arg in template[3:-1].split(',')]
    template_type = template[1]
    try:
        if template_type == 'a':
            # $a[4-11] all in 4-11, include both ends, used as a whole and repeat on every generation
            values = set()
            for arg in args:
                values.update(_collect_range_values(arg))
            return repeat(values)
        elif template_type == 'r':
            # $r[4, 11] random in 4-11, include both ends, return val
            # $r[4, 22, 1] random in 4-22, sampling step 1, include both ends, return val
            # $r[4, 99, 1, 10] random in 4-99, sampling step 1, include both ends, select 10, return list
            args = [int(arg) for arg in args]
            return make_random_producer(*args)
        elif template_type == 'e':
            # $e[1-100, 4-11] all in 1-100, exclude all in 4-11, include both ends, more args can be added for exclusion
            #  produce next value on every generation (cycle)
            values = set(_collect_range_values(args[0]))
            for arg in args[1:]:
                values.difference_update(_collect_range_values(arg))
            return cycle(values)
        else:
            assert template_type == 'c'
            # $c[1-10] all in 1-10, include both ends, produce next value on every generation (cycle)
            values = set()
            for arg in args:
                values.update(_collect_range_values(arg))
            return cycle(values)
    except Exception as e:
        raise ValueError(f'invalid template {template}') from e


def _collect_range_values(arg: str, range_ends_type: type[T] = int) -> Iterable[T]:
    begin_end = arg.split('-')
    if len(begin_end) == 2:
        for val in range(range_ends_type(begin_end[0]), range_ends_type(begin_end[1]) + 1):
            yield val
    else:
        yield range_ends_type(begin_end[0])


def apply_template(item, path: tuple, template_value_producer: Iterator):
    try:
        if not path:
            return next(template_value_producer)
        else:
            ref = item
            for i in path[:-1]:
                ref = ref[i]
            ref[path[-1]] = next(template_value_producer)
            return item
    except StopIteration:
        raise RuntimeError('template value producer early end')


def apply_templates(item, producers: dict[tuple, Iterator]):
    from copy import deepcopy
    item = deepcopy(item)
    for path, template_value_generator in producers.items():
        apply_template(item, path, template_value_generator)
    return item


def match_actors(actors: Iterable[str], pattern) -> list[str]:
    if not pattern:
        pattern = '.*'
    if isinstance(actors, str):
        raise TypeError('expected an iterable of str, got a str')
    return [actor_name for actor_name in actors if re.match(rf'^{pattern}$', actor_name)]
