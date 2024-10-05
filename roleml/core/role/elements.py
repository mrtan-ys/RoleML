from dataclasses import dataclass, field
from enum import Enum, auto
from io import IOBase
from typing import Any, Callable, Generic, Mapping, Optional, Literal

from roleml.shared.types import T

__all__ = ['ConstructStrategy', 'InitializeStrategy', 'Element', 'Factory', 'ElementImplementation']


class ConstructStrategy(Enum):
    ONCE = auto()
    ONCE_EAGER = auto()
    EVERY_CALL = auto()
    DEFAULT = ONCE


class InitializeStrategy(Enum):
    ONCE = auto()
    EVERY_CALL = auto()
    DEFAULT = ONCE


@dataclass
class Element(Generic[T]):

    cls: type[T]
    default_impl: Optional[T] = None

    default_constructor: Optional[Callable[..., T]] = None
    default_construct_strategy: ConstructStrategy = ConstructStrategy.DEFAULT
    default_constructor_args: Optional[Mapping[str, Any]] = None

    default_initializer: Optional[Callable[[T], None]] = None
    default_initialize_strategy: InitializeStrategy = InitializeStrategy.DEFAULT

    default_serializer: Optional[Callable[[T, IOBase], None]] = None
    default_serializer_mode: Literal['binary', 'text'] = 'binary'

    default_deserializer: Optional[Callable[[IOBase], T]] = None
    default_deserializer_mode: Literal['binary', 'text'] = 'binary'

    default_destructor: Optional[Callable[[T], None]] = None

    optional: bool = False      # if True, will not issue a warning if element is not implemented at RUNNING status

    type_check: bool = False

    @property
    def implemented(self) -> bool:
        return False

    def __call__(self, *args, **kwargs) -> T:
        raise RuntimeError(f'the element typed {self.cls.__name__} is not implemented')

    @property
    def serializable(self) -> bool:
        raise RuntimeError(f'the element typed {self.cls.__name__} is not implemented')

    @property
    def deserializable(self) -> bool:
        raise RuntimeError(f'the element typed {self.cls.__name__} is not implemented')

    def reset(self):
        raise RuntimeError(f'the element typed {self.cls.__name__} is not implemented')


@dataclass
class Factory(Element, Generic[T]):

    # lesson learnt: type annotation is required here in order to override base class
    default_construct_strategy: ConstructStrategy = ConstructStrategy.EVERY_CALL


@dataclass
class ElementImplementation(Generic[T]):

    cls: type[T] = object   # type: ignore
    impl: Optional[T] = None

    constructor: Optional[Callable[..., T]] = None
    construct_strategy: Optional[ConstructStrategy] = None
    constructor_args: Mapping[str, Any] = field(default_factory=dict)

    initializer: Optional[Callable[[T], None]] = None
    initialize_strategy: Optional[InitializeStrategy] = None

    serializer: Optional[Callable[[T, IOBase], None]] = None
    serializer_destination: Optional[str] = None
    serializer_mode: Optional[Literal['binary', 'text']] = None

    deserializer: Optional[Callable[[IOBase], T]] = None
    deserializer_source: Optional[str] = None
    deserializer_mode: Optional[Literal['binary', 'text']] = None

    destructor: Optional[Callable[[T], None]] = None
