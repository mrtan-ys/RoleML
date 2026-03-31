from collections.abc import Mapping
from typing import Any, Callable, Concatenate, Generic, Literal, NotRequired, Optional, TypeVar
from typing_extensions import TypedDict     # for extra_items

from roleml.shared.types import P, T


CallableType = TypeVar('CallableType', bound=Callable)  # each kind of method corresponds to a type of Callable


class MethodStore(Generic[CallableType]):

    def __init__(self, category_name: str, init_methods: Optional[Mapping[str, CallableType]] = None):
        self.category_name = category_name
        self._store: dict[str, CallableType] = dict(init_methods or {})

    def __getitem__(self, key: str) -> CallableType:
        try:
            return self._store[key]
        except KeyError:
            raise RuntimeError(f'"{key}" is not a valid {self.category_name} method')

    def __setitem__(self, key: str, value: CallableType):
        self._store[key] = value

    def get(self, key: str) -> Optional[CallableType]:
        return self._store.get(key)


# region built-in loader methods

class DirectUse(Generic[T]):

    def __init__(self, target: T):
        self.obj = target

    def __call__(self) -> T:
        return self.obj


class DirectImport(Generic[T]):

    def __init__(self, target: str):
        self.path = target

    def __call__(self) -> T:
        from roleml.shared.importing import load_definition
        return load_definition(self.path)


class Factory(Generic[T]):

    def __init__(self, target: str | Callable[..., T], args: Optional[Mapping[str, Any]] = None):
        if isinstance(target, str):
            from roleml.shared.importing import load_definition
            self.factory = load_definition(target)
        else:
            self.factory = target
        self.args = args or {}

    def __call__(self) -> T:
        return self.factory(**self.args)


class PickleDeserializer(Generic[T]):

    def __init__(self, target: str):
        self.target = target

    def __call__(self) -> T:
        import pickle
        with open(self.target, 'rb') as f:
            return pickle.load(f)


class JsonDeserializer(Generic[T]):

    def __init__(self, target: str):
        self.target = target

    def __call__(self) -> T:
        import json
        with open(self.target, 'r') as f:
            return json.load(f)

# endregion


loader_methods: MethodStore[Callable[..., Callable[[], Any]]] = MethodStore('loader', {
    'direct-use': DirectUse,
    'direct-import': DirectImport,
    'factory': Factory,
    'pickle': PickleDeserializer,
    'json': JsonDeserializer,
    'default': Factory,
})


# region built-in serializer methods

class PickleSerializer(Generic[T]):

    def __init__(self, target: str, base: Optional[type[T]] = None):
        self.target = target
        self.base = base

    def __call__(self, obj: T):
        if self.base is not None and not isinstance(obj, self.base):
            raise TypeError(f'pickling of {type(obj)!s} has been disabled')
        import pickle
        with open(self.target, 'wb') as file:
            pickle.dump(obj, file)


class JsonSerializer(Generic[T]):

    def __init__(self, target: str, base: Optional[type[T]] = None):
        self.target = target
        self.base = base

    def __call__(self, obj: T):
        if self.base is not None and not isinstance(obj, self.base):
            raise TypeError(f'{type(obj)!s} cannot be JSON serialized')
        import json
        with open(self.target, 'w') as file:
            json.dump(obj, file)

# endregion


serializer_methods: MethodStore[Callable[..., Callable[[Any], None]]] = MethodStore('serializer', {
    'pickle': PickleSerializer,
    'json': JsonSerializer,
})


# region built-in initializer methods

class BasicInitializer(Generic[T, P]):

    def __init__(self, target: str | Callable[Concatenate[Optional[T], P], T]):
        if isinstance(target, str):
            from roleml.shared.importing import load_definition
            self.func = load_definition(target)
        else:
            self.func = target

    def __call__(self, obj: Optional[T], *args, **kwargs) -> T:
        return self.func(obj, *args, **kwargs)


class FactoryInitializer(Generic[T, P]):

    def __init__(self, target: str | Callable[..., T]):
        if isinstance(target, str):
            from roleml.shared.importing import load_definition
            self.factory = load_definition(target)
        else:
            self.factory = target

    def __call__(self, _: Optional[T], *args, **kwargs) -> T:
        return self.factory(*args, **kwargs)

# endregion


initializer_methods: MethodStore[Callable[..., Callable[Concatenate[Optional[Any], ...], Any]]] = MethodStore('initializer', {
    'basic': BasicInitializer,
    'factory': FactoryInitializer,
})


# region built-in unloader methods

class BasicUnloader(Generic[T]):

    def __init__(self, target: str | Callable[[T], None]):
        if isinstance(target, str):
            from roleml.shared.importing import load_definition
            self.func = load_definition(target)
        else:
            self.func = target

    def __call__(self, obj: T):
        self.func(obj)

# endregion


unloader_methods: MethodStore[Callable[..., Callable[[Any], None]]] = MethodStore('unloader', {
    'basic': BasicUnloader,
})


ElementImplementationComponentSpec = TypedDict(
    'ElementImplementationComponentSpec',
    {'method': NotRequired[str]}, extra_items=Any
)


class ElementImplementationSpec(TypedDict, total=False):
    loader: ElementImplementationComponentSpec
    serializer: ElementImplementationComponentSpec
    initializer: ElementImplementationComponentSpec
    unloader: ElementImplementationComponentSpec
    eager_load: bool
