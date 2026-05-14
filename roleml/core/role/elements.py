from dataclasses import dataclass, field, KW_ONLY
from types import UnionType
from typing import Any, Callable, Concatenate, Generic, Literal, Optional
from typing_extensions import ParamSpec

from roleml.shared.types import T

__all__ = ['Element', 'InitializationParams']


IsInstanceArg = type[Any] | UnionType | tuple["IsInstanceArg", ...]

InitializationParams = ParamSpec('InitializationParams', default=...)   # mainly for type hints
MethodName = Literal["load", "initialize", "serialize", "unload", "get"]


@dataclass
class Element(Generic[T, InitializationParams]):

    cls: type[T]    # TODO is it better to use typing.TypeForm?

    default: Optional[T] = None
    default_factory: Optional[Callable[[], T]] = None   # higher priority
    default_initializer: Optional[Callable[Concatenate[Optional[T], InitializationParams], T]] = None

    _: KW_ONLY

    optional: bool = False

    type_check: bool = False    # disabled by default to prevent invalid isinstance() calls
    type_check_fallback: Optional[IsInstanceArg] = None

    def implemented(self, method_name: MethodName, /) -> bool:
        raise RuntimeError("should be called in a role instance")   # note: actually not calling `Element`

    def load(self) -> T:
        raise RuntimeError("should be called in a role instance")   # note: actually not calling `Element`

    def __call__(self) -> T:
        return self.load()

    def unload(self):
        raise RuntimeError("should be called in a role instance")   # note: actually not calling `Element`

    def get(self) -> T:
        raise RuntimeError("should be called in a role instance")   # note: actually not calling `Element`

    require_methods: set[MethodName] = field(default_factory=set)

    def serialize(self):
        raise RuntimeError("should be called in a role instance")   # note: actually not calling `Element`

    def initialize(self, *args: InitializationParams.args, **kwargs: InitializationParams.kwargs) -> T:
        raise RuntimeError("should be called in a role instance")   # note: actually not calling `Element`
