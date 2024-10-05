from abc import ABC, abstractmethod
from io import IOBase
from typing import Protocol, runtime_checkable


class Runnable(ABC):

    @abstractmethod
    def run(self): ...

    def stop(self):
        pass


@runtime_checkable
class Serializable(Protocol):

    def serialize(self, destination: IOBase): ...


@runtime_checkable
class Deserializable(Protocol):

    def deserialize(self, source: IOBase, **options): ...
