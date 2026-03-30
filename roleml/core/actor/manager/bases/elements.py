from abc import ABC, abstractmethod

from roleml.core.actor.manager.base import BaseManager
from roleml.core.role.elements import ElementImplementation


class BaseElementManager(BaseManager, ABC):

    @abstractmethod
    def implement_element(self, instance_name: str, element_name: str, impl: ElementImplementation):
        ...
