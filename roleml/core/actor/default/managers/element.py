import logging
from io import IOBase
from threading import RLock
from typing import Any, Generic, Optional

from roleml.core.actor.manager.bases import BaseElementManager
from roleml.core.role.base import Role
from roleml.core.role.elements import Element, ConstructStrategy, InitializeStrategy, ElementImplementation
from roleml.core.status import Status
from roleml.shared.types import T

__all__ = ['ElementInstance', 'ElementManager']


class ElementInstance(Generic[T]):

    __slots__ = ('logger', 'name', 'cls', 'type_check', 'constructor', 'construct_strategy', 'constructor_args',
                 'initializer', 'initialize_strategy', '_initialized', '_instance',
                 'serializer', 'serializer_destination', 'serializer_mode',
                 'deserializer', 'deserializer_source', 'deserializer_mode',
                 'destructor')

    def __init__(self, name: str, element: Element[T], impl: ElementImplementation[T]):
        self.logger = logging.getLogger('roleml.managers.element')
        self.name = name
        self.type_check = element.type_check
        if impl.cls not in (Any, object, None):
            if self.type_check and (not isinstance(impl.cls, type) or not issubclass(impl.cls, self.cls)):
                raise TypeError(f"incorrect type for element implementation of ({self.name}), "
                                f"expected {self.cls} or subclass, declared {impl.cls}")
            self.cls = impl.cls
        else:
            self.cls = element.cls

        # constructor
        if impl.constructor is not None:
            self.constructor = impl.constructor
        elif impl.cls not in (Any, object, None):
            self.constructor = impl.cls
        elif element.default_constructor is not None:
            self.constructor = element.default_constructor
        else:
            self.constructor = None     # to use element.cls, set it as element.default_constructor
        self.construct_strategy = impl.construct_strategy or element.default_construct_strategy
        self.constructor_args = impl.constructor_args or element.default_constructor_args or {}

        # initializer
        self.initializer = impl.initializer or element.default_initializer
        self.initialize_strategy = impl.initialize_strategy or element.default_initialize_strategy

        # serializer
        self.serializer = impl.serializer or element.default_serializer
        self.serializer_destination = impl.serializer_destination
        self.serializer_mode = impl.serializer_mode or element.default_serializer_mode

        # deserializer
        self.deserializer = impl.deserializer or element.default_deserializer
        self.deserializer_source = impl.deserializer_source
        self.deserializer_mode = impl.deserializer_mode or element.default_deserializer_mode

        # destructor
        self.destructor = impl.destructor or element.default_destructor

        self._initialized = False
        if impl.impl is not None:
            self._instance = impl.impl
        elif self.deserializer and self.deserializer_source:
            self.deserialize()
        elif self.constructor:
            self._instance = None
            if self.construct_strategy == ConstructStrategy.ONCE_EAGER:
                self.construct()
        elif element.default_impl is not None:
            self._instance = element.default_impl
        else:
            raise RuntimeError(f'no provider for element {self.name}')

    @property
    def read_mode(self):
        return 'r' if self.deserializer_mode == 'text' else 'rb'

    @property
    def write_mode(self):
        return 'w' if self.serializer_mode == 'text' else 'wb'

    def construct(self, *args, **kwargs):
        if not self.constructor:
            raise RuntimeError(f"constructor is not provided for element ({self.name})")
        self.reset()     # destruct previous instance (if any)
        if args or kwargs:
            self._instance = self.constructor(*args, **kwargs)
        else:
            self._instance = self.constructor(**self.constructor_args)
        if self.type_check and not isinstance(self._instance, self.cls):
            raise TypeError(f"incorrect type for element implementation of ({self.name}), "
                            f"expected {self.cls}, constructed {type(self._instance)}")
        self._initialized = False

    def serialize(self, file: Optional[IOBase] = None):
        if file:
            self._serialize(file)
        else:
            if not self.serializer_destination:
                raise RuntimeError(f'serializer destination is not provided for element {self.name}')
            with open(self.serializer_destination, self.write_mode) as file:
                # file will be truncated first
                self._serialize(file)
    
    def serialize_if_possible(self):
        if self.serializer_destination:
            with open(self.serializer_destination, self.write_mode) as file:
                # file will be truncated first
                self._serialize(file)
    
    def _serialize(self, file: IOBase):
        if self.serializer is None:
            raise RuntimeError(f"serializer is not provided for element {self.name}")
        if self._instance is None:
            raise RuntimeError(f"no instance to serialize for element {self.name}")
        self.serializer(self._instance, file)

    def deserialize(self, file: Optional[IOBase] = None) -> T:
        if file:
            return self._deserialize(file)
        else:
            if not self.deserializer_source:
                raise RuntimeError(f'deserializer source is not provided for element {self.name}')
            with open(self.deserializer_source, self.read_mode) as file:
                return self._deserialize(file)

    def _deserialize(self, file: IOBase):
        if self.deserializer is None:
            raise RuntimeError(f"deserializer is not provided for element {self.name}")
        self._instance = self.deserializer(file)
        self._initialized = True
        return self._instance

    # below corresponds to user APIs

    def __call__(self, *args, **kwargs) -> T:
        # constructed?
        if self._instance is None or self.construct_strategy == ConstructStrategy.EVERY_CALL:
            self.construct(*args, **kwargs)
        elif args or kwargs:
            self.logger.warning('trying to call an element with args or kwargs, but the construction strategy does '
                                'not allow reconstruction. The args or kwargs provided will be ignored')
        assert self._instance is not None
        # initialized?
        if not self._initialized or self.initialize_strategy == InitializeStrategy.EVERY_CALL:
            if self.initializer:
                self.initializer(self._instance)
            self._initialized = True
        return self._instance

    @property
    def implemented(self):
        return (self._instance is not None) or (self.constructor is not None)

    @property
    def serializable(self):
        return self.serializer is not None

    @property
    def deserializable(self):
        return self.deserializer is not None

    def reset(self):
        if self._instance is not None:
            if self.destructor is not None:
                self.destructor(self._instance)
            self._instance = None


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
                        setattr(role, attribute_name, element_instance)
                    except Exception as e:
                        if not element.optional:
                            self.logger.warning(f'cannot implement element {element_name} of role {instance_name} '
                                                f'using default specification: {e}')
                    else:
                        if not element_instance.implemented and not element.optional:
                            self.logger.warning(f'element {element_name} is not properly implemented for role '
                                                f'{instance_name}, instance is {element_instance._instance}')
                        else:
                            self.logger.info(f'element {element_name} of role {instance_name} implemented as default')

    def _on_role_status_finalizing(self, instance_name: str, _):
        with self.lock:
            role = self.roles[instance_name]
            for element_name, attribute_name in role.__class__.elements.items():
                el = getattr(role, attribute_name)
                if isinstance(el, ElementInstance):
                    if el.serializable:
                        el.serialize_if_possible()  # only serialize when serializer_destination is provided
                    el.reset()
                    self.logger.info(f'element {element_name} of role {instance_name} has been reset')
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
