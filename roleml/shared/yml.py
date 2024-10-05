from pathlib import Path
from typing import Any

from yaml import MappingNode, ScalarNode, YAMLError, load, safe_dump
from yaml.composer import Composer
from yaml.constructor import SafeConstructor
from yaml.parser import Parser
from yaml.reader import Reader
from yaml.resolver import Resolver
from yaml.scanner import Scanner

__all__ = ['IncludeConstructor', 'Loader', 'save_yaml', 'load_yaml', 'ObjectFromYAML']


class IncludeConstructor(SafeConstructor):

    def construct_mapping(self, node, deep: Any = False):
        """ XXX this function now iterates over the value nodes twice (instead of once) """
        included = {}
        if isinstance(node, MappingNode):
            index = 0
            while index < len(node.value):
                key_node, value_node = node.value[index]
                if key_node.tag == 'tag:yaml.org,2002:merge' \
                        and isinstance(value_node, ScalarNode) and value_node.tag == '!include':
                    val = self.construct_object(value_node)
                    if not isinstance(val, dict):
                        raise TypeError(f'Element included for mapping merging must be another mapping, '
                                        f'found {type(val)}')
                    included.update(val)
                    del node.value[index]
                else:
                    index += 1
            self.flatten_mapping(node)
        constructed = super().construct_mapping(node, deep=deep)
        constructed.update(included)
        return constructed


class Loader(Reader, Scanner, Parser, Composer, IncludeConstructor, Resolver):

    def __init__(self, stream):
        self._root = Path(getattr(stream, 'name', stream)).parent

        Reader.__init__(self, stream)
        Scanner.__init__(self)
        Parser.__init__(self)
        Composer.__init__(self)
        IncludeConstructor.__init__(self)
        Resolver.__init__(self)

    def include(self, node):
        name = str(self.construct_scalar(node)).split(' ')
        if len(name) == 0 or len(name) > 2:
            raise YAMLError('The !include command must have 1-2 arguments')
        filename = self._root / name[0]
        with open(filename, 'r') as file:
            document = load(file, Loader)
        if len(name) == 2:
            index_path = name[1].split('.')
            try:
                for index in index_path:
                    document = document[index]
            except KeyError as e:
                raise YAMLError(f'Cannot include element {name[1]} in file {filename!s}, missing key/idx {e}')
        return document


Loader.add_constructor('!include', Loader.include)


def save_yaml(filename, obj):
    with open(filename, 'w') as file:
        safe_dump(obj, file)


def load_yaml(filename):
    with open(filename) as file:
        return load(file, Loader)


ObjectFromYAML = load_yaml
