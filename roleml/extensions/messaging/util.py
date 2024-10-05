from typing import Any, MutableMapping, Mapping

from roleml.core.messaging.types import Tags


def insert_tags(dest: MutableMapping[str, Any], tags: Tags):
    for key, value in tags.items():
        # avoid a tag key with underscore from being filtered out (e.g. in newer versions of Flask/werkzeug)
        dest[f'RoleML-{key.replace("_", "-")}'] = value


class TagReader(Mapping):

    def __init__(self, src: Mapping[str, Any]):
        self._src = src

    def __getitem__(self, key: str) -> Any:
        return self._src[f'RoleML-{key.replace("_", "-")}']

    def __len__(self):
        total = 0
        for key in self._src:
            if key.startswith('_') and key.endswith('_'):
                total += 1
        return total

    def __iter__(self):
        for key in self._src:
            if key.startswith('_') and key.endswith('_'):
                yield key


def is_namedtuple(obj):
    return hasattr(obj, '_asdict')
