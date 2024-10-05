from io import IOBase
from typing import Any, Callable, TypedDict, Union, cast

from roleml.core.role.elements import ConstructStrategy, ElementImplementation, InitializeStrategy
from roleml.shared.importing import Descriptor, LoadCompatible, as_definition, load


# region initializers

def _initialize_by_self(obj):
    obj.initialize()


_registered_initializers = {
    'self': lambda: _initialize_by_self
}   # type: dict[str, Callable[[], Callable[[Any], None]]]


def get_registered_initializer(name: str) -> Callable[[Any], None]:
    try:
        return _registered_initializers[name]()
    except KeyError:
        raise RuntimeError(f'cannot find initializer named {name}')


def register_initializer(name: str, getter: Callable[[], Callable[[Any], None]]):
    _registered_initializers[name] = getter

# endregion


# region serializers

def _serialize_by_self(obj, file: IOBase):
    obj.serialize(file)


def get_pickle_serializer():
    import pickle
    return pickle.dump


def get_json_serializer():
    import json
    return json.dump


_registered_serializers = {
    'self': lambda: _serialize_by_self,
    'pickle': get_pickle_serializer,
    'json': get_json_serializer
}   # type: dict[str, Callable[[], Callable[[Any, IOBase], None]]]


def get_registered_serializer(name: str) -> Callable[[Any, IOBase], None]:
    try:
        return _registered_serializers[name]()
    except KeyError:
        raise RuntimeError(f'cannot find serializer named {name}')


def register_serializer(name: str, getter: Callable[[], Callable[[Any, IOBase], None]]):
    _registered_serializers[name] = getter

# endregion


# region deserializers

def get_pickle_deserializer():
    import pickle
    return pickle.load


def get_json_deserializer():
    import json
    return json.load


_registered_deserializers = {
    'pickle': get_pickle_deserializer,
    'json': get_json_deserializer
}   # type: dict[str, Callable[[], Callable[[IOBase], Any]]]


def get_registered_deserializer(name: str) -> Callable[[IOBase], Any]:
    try:
        return _registered_deserializers[name]()
    except KeyError:
        raise RuntimeError(f'cannot find deserializer named {name}')


def register_deserializer(name: str, getter: Callable[[], Callable[[IOBase], Any]]):
    _registered_deserializers[name] = getter

# endregion


ElementImplementationSpec = TypedDict('ElementImplementationSpec', {
    'class': Descriptor[type],
    'impl': Union[str, Any],
    'constructor': LoadCompatible[Callable],
    'construct_strategy': Union[str, ConstructStrategy],
    'constructor_args': dict[str, Any],
    'initializer': LoadCompatible[Callable],
    'initialize_strategy': Union[str, InitializeStrategy],
    'serializer': LoadCompatible[Callable],
    'serializer_destination': str,
    'deserializer': LoadCompatible[Callable],
    'deserializer_source': str,
    'destructor': LoadCompatible[Callable]
}, total=False)


ParsedElementImplementationSpec = TypedDict('ParsedElementImplementationSpec', {
    'class': type,
    'impl': object,
    'constructor': Callable,
    'construct_strategy': ConstructStrategy,
    'constructor_args': dict[str, Any],
    'initializer': Callable,
    'initialize_strategy': InitializeStrategy,
    'serializer': Callable,
    'serializer_destination': str,
    'deserializer': Callable,
    'deserializer_source': str,
    'destructor': Callable
}, total=False)


def load_element_impl_spec(spec: ElementImplementationSpec) -> ElementImplementation:
    kwargs = cast(dict[str, Any], parse_descriptors(spec))
    if 'class' in kwargs:
        kwargs['cls'] = kwargs.pop('class')
    return ElementImplementation(**kwargs)


def parse_descriptors(spec: ElementImplementationSpec) -> ParsedElementImplementationSpec:
    spec_parsed = spec.copy()
    if construct_strategy := spec.get('construct_strategy'):
        if isinstance(construct_strategy, str):
            spec_parsed['construct_strategy'] = ConstructStrategy[construct_strategy.upper()]
        else:
            spec_parsed['construct_strategy'] = construct_strategy
    if initialize_strategy := spec.get('initialize_strategy'):
        if isinstance(initialize_strategy, str):
            spec_parsed['initialize_strategy'] = InitializeStrategy[initialize_strategy.upper()]
        else:
            spec_parsed['initialize_strategy'] = initialize_strategy
    if cls := spec.get('class'):
        spec_parsed['class'] = as_definition(cls)
    if impl := spec.get('impl'):
        spec_parsed['impl'] = as_definition(impl)
    if constructor := spec.get('constructor'):
        spec_parsed['constructor'] = load(constructor, Callable)
    if initializer := spec.get('initializer'):
        spec_parsed['initializer'] = load(initializer, Callable, builtin_source_getters=_registered_initializers)
    if serializer := spec.get('serializer'):
        spec_parsed['serializer'] = load(serializer, Callable, builtin_source_getters=_registered_serializers)
    if deserializer := spec.get('deserializer'):
        spec_parsed['deserializer'] = load(deserializer, Callable, builtin_source_getters=_registered_serializers)
    if destructor := spec.get('destructor'):
        spec_parsed['destructor'] = load(destructor, Callable)
    return cast(ParsedElementImplementationSpec, spec_parsed)
