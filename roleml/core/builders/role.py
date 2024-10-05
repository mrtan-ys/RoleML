from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, ClassVar, Final, Generic, Literal, NamedTuple, Optional, TypeAlias, Union
from typing_extensions import TypedDict, Required

from roleml.core.actor.base import BaseActor
from roleml.core.builders.element import ElementImplementationSpec, load_element_impl_spec
from roleml.core.builders.helpers import RoleType
from roleml.core.role.base import Role
from roleml.core.role.elements import ElementImplementation
from roleml.shared.importing import as_class

__all__ = ['RoleDescriptor', 'RoleSpec', 'ElementSpecConflictResolveStrategy', 'RoleElementPresetSpec', 'RoleBuilder']


RoleDescriptor: TypeAlias = Union[str, type[Role]]


RoleSpec = TypedDict('RoleSpec', {
    'class': Required[RoleDescriptor],
    'options': dict[str, Any],
    'impl': dict[str, ElementImplementationSpec]
}, total=False)


class RoleConfig(NamedTuple):
    cls: RoleDescriptor
    options: dict[str, Any] = {}
    impl: dict[str, ElementImplementationSpec] = {}


ElementSpecConflictResolveStrategy: TypeAlias = Literal['preset', 'override', 'error']


class RoleElementPresetSpec(TypedDict, total=False):
    elements: dict[str, ElementImplementationSpec]
    on_conflict: ElementSpecConflictResolveStrategy


@dataclass
class RoleElementPreset:
    elements: dict[str, ElementImplementationSpec] = field(default_factory=dict)
    on_conflict: ElementSpecConflictResolveStrategy = 'override'


class RoleBuilder(Generic[RoleType]):
    # not thread-safe, but should be OK

    element_preset_registry: ClassVar[defaultdict[type[Role], RoleElementPreset]] = defaultdict(RoleElementPreset)

    @staticmethod
    def update_element_preset(
            role_cls: RoleDescriptor, elements: Optional[dict[str, ElementImplementationSpec]] = None,
            on_conflict: Optional[ElementSpecConflictResolveStrategy] = None):
        if not elements and not on_conflict:
            return
        actual_role_cls = as_class(role_cls)
        if not issubclass(actual_role_cls, Role):
            raise TypeError('element preset can only be updated for a role class')
        preset = RoleBuilder.element_preset_registry[actual_role_cls]
        if elements:
            preset.elements.update(elements)
        if on_conflict:
            preset.on_conflict = on_conflict

    @staticmethod
    def find_element_preset(role_cls: type[Role]) -> Optional[RoleElementPreset]:
        if element_preset := RoleBuilder.element_preset_registry.get(role_cls):
            return element_preset
        bases = role_cls.__bases__
        for base in bases:
            if issubclass(base, Role):
                return RoleBuilder.find_element_preset(base)
        return None

    @staticmethod
    def clear_element_preset():
        # for unit tests only
        RoleBuilder.element_preset_registry = defaultdict(RoleElementPreset)

    name: Final[str]
    config: Final[RoleConfig]

    def __init__(self, name: str, spec: Union[str, RoleSpec]):
        # do not modify these attributes after build() called
        self.name = name
        if isinstance(spec, str):
            self.config = RoleConfig(spec)
        else:
            self.config = RoleConfig(spec['class'], spec.get('options', {}), spec.get('impl', {}))
        
        # fulfilled when calling build(), user need not interact with these
        self.role: Optional[Role] = None
        self.impls: dict[str, ElementImplementation] = {}

    def build(self):
        if self.role is not None:
            return  # role already built

        role_class: type[Role] = as_class(self.config.cls)
        if not issubclass(role_class, Role):
            raise TypeError(f'invalid role class {role_class}')

        # find an element preset that can be applied
        if element_preset := RoleBuilder.find_element_preset(role_class):
            preset_elements = element_preset.elements
            conflict = set(preset_elements).intersection(set(self.config.impl))
            if conflict:
                if element_preset.on_conflict == 'override':
                    for element_name, spec in preset_elements.items():
                        self.config.impl.setdefault(element_name, spec)
                elif element_preset.on_conflict == 'preset':
                    self.config.impl.update(preset_elements)
                else:
                    # TODO find a more appropriate error type
                    raise TypeError(f'role element specification conflict with preset: {conflict}')
            else:
                self.config.impl.update(preset_elements)

        self.role = role_class(**self.config.options)
        self.impls = {}
        if self.config.impl:
            for element_name, spec in self.config.impl.items():
                self.impls[element_name] = load_element_impl_spec(spec)

    def install(self, actor: BaseActor, start: bool = False):
        if self.role is None:
            raise RuntimeError('role is not built yet, please call build() first')
        actor.add_role(self.name, self.role)
        if elements := self.impls:
            for element_name, element_impl in elements.items():
                actor.implement_element(self.name, element_name, element_impl)
        if start:
            actor.start_role(self.name)
