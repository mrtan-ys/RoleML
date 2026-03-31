from abc import ABC, abstractmethod
from dataclasses import KW_ONLY, dataclass
from typing import Callable, Concatenate, Generic, Optional, Protocol, TypeAlias, runtime_checkable

from roleml.core.actor.manager.base import BaseManager
from roleml.core.role.elements import Element, InitializationParams
from roleml.shared.types import T


ElementLoader: TypeAlias = Callable[[], T]
ElementSerializer: TypeAlias = Callable[[T], None]
ElementInitializer: TypeAlias = Callable[Concatenate[Optional[T], ...], T]
ElementUnloader: TypeAlias = Callable[[T], None]


@dataclass
class ElementImplementation(Generic[T]):

    loader: Optional[ElementLoader[T]] = None
    serializer: Optional[ElementSerializer] = None
    initializer: Optional[ElementInitializer] = None
    unloader: Optional[ElementUnloader] = None

    _: KW_ONLY

    eager_load: bool = False


@runtime_checkable
class SetupWithElement(Protocol[T, InitializationParams]):

    def setup(self, element: Element[T, InitializationParams]):
        ...


class BaseElementManager(BaseManager, ABC):

    @abstractmethod
    def implement_element(self, instance_name: str, element_name: str, impl: ElementImplementation):
        ...
