import logging
from threading import RLock
from typing import Generic, Optional

from roleml.core.actor.manager.bases.elements import BaseElementManager, ElementImplementation, SetupWithElement
from roleml.core.role.base import Role
from roleml.core.role.elements import Element, InitializationParams
from roleml.core.status import Status
from roleml.shared.types import T

__all__ = ['ElementInstance', 'ElementManager']


class ElementInstance(Generic[T, InitializationParams]):

    def __init__(self, name: str, element: Element[T, InitializationParams], impl: ElementImplementation[T]):
        self.name = name
        self.logger = logging.getLogger('roleml.managers.element')

        self._instance: Optional[T] = None

        self.cls = element.cls
        self.default = element.default
        self.default_factory = element.default_factory
        self.optional = element.optional
        self.type_check = element.type_check
        self.type_check_fallback = element.type_check_fallback
        self.require_serializable = element.require_serializable

        if impl.eager_load:
            if impl.loader is not None:
                self._instance = impl.loader()
            else:
                if element.default_factory is not None:
                    self._instance = element.default_factory()
                elif element.default is not None:
                    self._instance = element.default
            self.attempt_type_check_if_enabled()

        self.loader = impl.loader if impl.loader is not None else element.default_factory
        self.serializer = impl.serializer
        self.initializer = impl.initializer if impl.initializer is not None else element.default_initializer
        self.unloader = impl.unloader

        for component in (self.loader, self.serializer, self.initializer, self.unloader):
            if isinstance(component, SetupWithElement):
                component.setup(element)
        
        if element.require_serializable and not self.serializable:
            raise RuntimeError(f'element {self.name} is not serializable as required')

    @property
    def implemented(self) -> bool:
        return (self._instance is not None) or (self.loader is not None) or (self.initializer is not None)

    def attempt_type_check_if_enabled(self):
        if self.type_check and self._instance is not None:
            expected_type = self.type_check_fallback if self.type_check_fallback is not None else self.cls
            if not isinstance(self._instance, expected_type):
                raise TypeError(
                    f'invalid object type for element {self.name}, expected {self.cls!s}, got {type(self._instance)!s}')

    def load(self) -> T:
        if self.loader is None:
            raise RuntimeError(f"no way to load new object for element {self.name}")
        return self.__load()

    def __load(self) -> T:
        assert self.loader is not None
        if self._instance is not None:
            if self.unloader is not None:
                self.unloader(self._instance)
            self._instance = None
        self._instance = self.loader()
        assert self._instance is not None
        self.attempt_type_check_if_enabled()
        return self._instance

    def __call__(self) -> T:
        return self.load()

    def unload(self):
        if self._instance is None:
            raise RuntimeError(f"nothing to unload in element {self.name}")
        if self.unloader is not None:
            self.unloader(self._instance)
        self._instance = None

    def get(self) -> T:
        if self._instance is not None:
            return self._instance
        if self.loader is not None:
            self._instance = self.loader()
            return self._instance
        if self.default_factory is not None:
            self._instance = self.default_factory()
            return self._instance
        if self.default is not None:
            self._instance = self.default
            return self._instance
        raise RuntimeError(f"cannot get object for element {self.name}")

    @property
    def serializable(self) -> bool:
        return self.serializer is not None

    def serialize(self):
        if self.serializer is not None:
            if self._instance is not None:
                self.serializer(self._instance)
            else:
                raise RuntimeError(f"no object to serialize for element {self.name}")
        else:
            raise RuntimeError(f"no way to serialize object for element {self.name}")

    def initialize(self, *args: InitializationParams.args, **kwargs: InitializationParams.kwargs) -> T:
        if self.initializer is not None:
            self._instance = self.initializer(self._instance, *args, **kwargs)
            self.attempt_type_check_if_enabled()
            return self._instance
        else:
            if self.loader is None:
                raise RuntimeError(f"no way to load new object for element {self.name}")
            self.unload()
            return self.__load()


class EmptyElementInstance(Generic[T]):

    def __init__(self, name: str, element: Element[T]):
        self.name = name
        self.cls = element.cls
        self.default = element.default
        self.default_factory = element.default_factory
        self.optional = element.optional
        self.type_check = element.type_check
        self.type_check_fallback = element.type_check_fallback
        self.require_serializable = element.require_serializable

    @property
    def implemented(self) -> bool: return False
    def load(self) -> T: raise RuntimeError(f"element {self.name} not available")
    def __call__(self) -> T: return self.load()
    def unload(self): raise RuntimeError(f"element {self.name} not available")
    def get(self) -> T: raise RuntimeError(f"element {self.name} not available")
    @property
    def serializable(self) -> bool: return False
    def serialize(self): raise RuntimeError(f"element {self.name} not available")
    def initialize(self, *args, **kwargs) -> T: raise RuntimeError(f"element {self.name} not available")


class ElementManager(BaseElementManager):

    roles: dict[str, Role]
    lock: RLock

    def initialize(self):
        self.roles = {}
        self.lock = RLock()
        self.logger = logging.getLogger('roleml.managers.element')
        self.role_status_manager.add_callback(Status.STARTING, self._on_role_status_starting)
        self.role_status_manager.add_callback(Status.FINALIZING, self._on_role_status_finalizing)

    def add_role(self, role: Role):
        with self.lock:
            self.roles[role.name] = role

    def _on_role_status_starting(self, instance_name: str, _):
        with self.lock:
            role = self.roles[instance_name]
            for element_name, attribute_name in role.__class__.elements.items():
                if not isinstance(getattr(role, attribute_name), ElementInstance):  # we may get attr in __class__
                    # not implemented by config, try implement with default now
                    element: Element = getattr(role.__class__, attribute_name)
                    try:
                        element_instance = ElementInstance(element_name, element, ElementImplementation())
                    except Exception as e:
                        # e.g., when not serializable as required, or when default implementation does not match cls
                        if element.optional:
                            self.logger.warning(
                                f'cannot implement element {element_name} of role {instance_name} '
                                f'with default specification: {e}')
                            setattr(role, attribute_name, EmptyElementInstance(element_name, element))
                        else:
                            self.logger.error(
                                f'cannot implement element {element_name} of role {instance_name} '
                                f'with default specification: {e}')
                            self.logger.error(f'role {instance_name} is unusable as element {element_name} is required')
                            raise
                    else:
                        if not element_instance.implemented and not element.optional:
                            self.logger.error(
                                f'element {element_name} is not properly implemented for role '
                                f'{instance_name}, instance is of type {type(element_instance._instance)}')
                            self.logger.error(f'role {instance_name} is unusable as element {element_name} is required')
                            raise RuntimeError(f'required element {element_name} of role {instance_name} unimplemented')
                        else:
                            self.logger.info(f'element {element_name} of role {instance_name} implemented as default')
                            setattr(role, attribute_name, element_instance)

    def _on_role_status_finalizing(self, instance_name: str, _):
        with self.lock:
            role = self.roles[instance_name]
            for element_name, attribute_name in role.__class__.elements.items():
                el = getattr(role, attribute_name)
                if isinstance(el, ElementInstance):
                    if el.serializable:
                        try:
                            el.serialize()  # TODO consider adding a `serialize_on_finalizing` option
                        except Exception as e:
                            self.logger.warning(f'cannot serialize element {el.name} when finalizing')
                        else:
                            self.logger.info(f'element {element_name} of role {instance_name} has been serialized')
                    el.unload()
                    self.logger.info(f'element {element_name} of role {instance_name} has been unloaded')
            del self.roles[instance_name]

    def implement_element(self, instance_name: str, element_name: str, impl: ElementImplementation):
        with self.lock:
            try:
                role = self.roles[instance_name]
                element = getattr(role, role.__class__.elements[element_name])
            except (KeyError, AttributeError):
                self.logger.warning(f'attempting to implement a non-existent element {instance_name}/{element_name}')
                raise RuntimeError(f'no such element: {instance_name}/{element_name}')
            if not isinstance(element, Element):
                self.logger.warning(f'attempting to re-implement element {instance_name}/{element_name}')
                raise RuntimeError(f'element {instance_name}/{element_name} already implemented')
            setattr(role, role.__class__.elements[element_name], ElementInstance(element_name, element, impl))
            self.logger.info(f'element {element_name} of role {instance_name} implemented')
