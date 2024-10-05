import importlib
from collections.abc import Mapping
from typing import Any, Callable, Generic, Optional, TypeVar, Union

from typing_extensions import TypedDict, Required, TypeAlias, TypeGuard

from roleml.shared.types import T

__all__ = ['AnyType', 'AnyCallable', 'Descriptor', 'load_definition', 'as_class', 'as_function', 'as_definition',
           'Spec', 'LoadCompatible', 'Loadable', 'load']


AnyType = TypeVar('AnyType', bound=type)
AnyCallable = TypeVar('AnyCallable', bound=Callable)

Descriptor: TypeAlias = Union[str, T]


def load_definition(full_path: str) -> Any:
    """ Find and load a definition (function, class, or any other Python object).

    Args:
        full_path (str): the fully qualified name of the corresponding module and the name of the definition,
            separated by a dot.

    Returns:
        The function, class, or any other Python object found.

    Raises:
        AttributeError: the definition cannot be found in the given path.
        ModuleNotFoundError: the module cannot be found.
        ValueError: the given path is invalid.

    Examples:
        >>> load_definition('foo.roles.MyRole')      # will load the class `MyRole` in `foo.roles` module
    """
    try:
        module_name, attr_name = full_path.rsplit('.', 1)
    except ValueError:
        raise ValueError(f'cannot load invalid path {full_path}') from None
    module = importlib.import_module(module_name)
    return getattr(module, attr_name)


def as_class(type_or_path: Descriptor[AnyType]) -> AnyType:
    if isinstance(type_or_path, type):
        return type_or_path
    else:
        return load_definition(type_or_path)


def as_function(func_or_path: Descriptor[AnyCallable]) -> AnyCallable:
    if callable(func_or_path):
        return func_or_path
    else:
        return load_definition(func_or_path)


def as_definition(descriptor: Descriptor[T]) -> T:
    """ WARNING: if `descriptor` is a str, it will always be treated as a fully qualified name. """
    if isinstance(descriptor, str):
        return load_definition(descriptor)
    else:
        return descriptor


class Spec(TypedDict, Generic[T], total=False):
    type: Required[Union[str, Callable[..., T]]]
    options: dict[str, Any]


def is_spec(d: Mapping[str, Any]) -> TypeGuard[Spec]:
    # no type check, make sure a mapping is passed
    if len(d) >= 3 or 'type' not in d:
        return False
    return len(d) == 1 or ('options' in d)


LoadCompatible: TypeAlias = Union[str, T, Callable[..., T], Spec[T]]
Loadable: TypeAlias = Union[str, Callable[..., T], Spec[T]]


def load(target: LoadCompatible[T], obj_type: type[T],
         *, args: Optional[tuple] = None, kwargs: Optional[dict[str, Any]] = None,
         builtin_sources: Optional[dict[str, Any]] = None,
         builtin_source_getters: Optional[dict[str, Callable[[], Any]]] = None) -> T:
    """
    Load and instantiate an object, which should be of type `obj_type`.

    How the object is loaded depends on the type of the input `target`:

    * **str**: will be treated in the following order until an object is found or imported: (1) the name of an object
      previously-registered to `builtin_sources`; (2) the name of an object getter previously-registered to
      `builtin_source_getters`, in which case the getter will be called with no arguments; (3) a fully-qualified name of
      the target object, which will be used in an importing process. If the object loaded is not an instance of
      `obj_type` but is callable (e.g., the corresponding class is loaded), it will be called to get an object, unless
      `obj_type` is `typing.Callable` (i.e., only looking for a callable object).
    * **Spec[T]**: the `type` of the spec will be treated as the constructor (when imported) and will be used to
      construct an object using arguments provided in `options` in the spec (if available) plus `args` and `kwargs`.
      if the same keyword is seen in both `options` and `kwargs`, the one in `options` will be overridden. Note that
      `type` can be either a str (treated in the same way as a str `target` in terms of object finding) or a class.
    * **otherwise**: will be treated as the desired object or, if callable and `target` is not an instance of `obj_type`
      and `obj_type` is not `Callable`, will be treated as a constructor and called with no arguments to get an object
      of type `obj_type`.

    If the loaded or constructed object is not of type `obj_type`, a `TypeError` will be raised.

    Also note that this function is NOT meant for loading a class. Even if `obj_type` is a protocol, this function will
    try to load an instance of a class that conforms to the protocol.
    """
    if obj_type is str:
        raise TypeError('load() does not support using str as the type')    # this is to avoid ambiguity

    if builtin_sources is None:
        builtin_sources = {}
    if builtin_source_getters is None:
        builtin_source_getters = {}

    expect_general_callable = obj_type is Callable  # OK although the type checker may report an error
    force_construct = False
    construct_options = {}

    def find_definition(name: str) -> Any:
        if name in builtin_sources:
            return builtin_sources[name]
        if name in builtin_source_getters:
            return builtin_source_getters[name]()
        return as_definition(name)

    # parse `target`
    if isinstance(target, str):
        loaded = find_definition(target)
    elif isinstance(target, dict) and is_spec(target):
        typ = target['type']
        loaded = find_definition(typ) if isinstance(typ, str) else typ
        force_construct = True
        construct_options = target.get('options', {})
    else:
        loaded = target
    
    if isinstance(loaded, obj_type):
        if isinstance(loaded, type):
            # a class can be an instance of a Protocol
            force_construct = True
        else:
            return loaded

    if callable(loaded):
        # only use callable to construct when:
        # 1. it is forced to do so (force_construct == True), or
        # 2. we are not just looking for a callable, and the already-loaded object (`loaded`) is not a subclass of
        #    the desired type (avoid incorrect construction when `loaded` is an instance of a class with `__call__`
        #    implemented)
        if force_construct or (not expect_general_callable and not isinstance(loaded, obj_type)):
            if isinstance(loaded, type) and isinstance(obj_type, type) and not issubclass(loaded, obj_type):
                raise TypeError(f'expected {obj_type}, got {loaded} instead')
            construct_options = construct_options.copy()
            construct_options.update(kwargs or {})
            loaded = loaded(*args or (), **construct_options)
            if isinstance(loaded, obj_type):
                return loaded

    raise TypeError(f'expected {obj_type}, got {loaded.__class__} instead')
