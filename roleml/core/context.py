import os
import random
import sys
import time
from collections.abc import Set
from types import MappingProxyType
from typing import NamedTuple, TypedDict, Union, Iterable, Optional, Mapping

from roleml.shared.multithreading.synchronization.simple import Locked


class ActorProfile(NamedTuple):
    name: str
    address: str

    def __eq__(self, other):
        if isinstance(other, ActorProfile):
            return other.name == self.name
        return NotImplemented


class ActorProfileSpec(TypedDict):
    name: str
    address: str


class RoleInstanceID(NamedTuple):
    actor_name: str
    instance_name: str

    def __str__(self):
        return f'{self.actor_name}/{self.instance_name}'
    
    @staticmethod
    def of(fullname: str) -> 'RoleInstanceID':
        names = fullname.split('/')
        if len(names) != 2:
            raise ValueError('invalid role instance fullname')
        return RoleInstanceID(names[0], names[1])


RoleInstanceIDTuple = tuple[str, str]
""" Don't use this unless when receiving event messages; put RoleInstanceID in payloads otherwise. """


def parse_instances(spec: Union[Iterable[str], str], default_instance_name: str = 'actor') -> list[RoleInstanceID]:
    if isinstance(spec, str):
        spec = [spec]
    instances = []
    for target in spec:
        split = target.rsplit('/', maxsplit=2)
        if len(split) == 2:
            instances.append(RoleInstanceID(split[0], split[1]))
        elif len(split) == 1:
            instances.append(RoleInstanceID(split[0], default_instance_name))
        else:
            continue
    return instances


class ActorNotFoundError(Exception):
    pass


class Contacts(Locked, synchronize_all=True):

    def __init__(self, *initial_contacts: ActorProfile):
        self._contacts: dict[str, ActorProfile] = {}
        if initial_contacts:
            for profile in initial_contacts:
                self._contacts[profile.name] = profile

    def add_contact(self, profile: ActorProfile) -> Optional[ActorProfile]:
        old_profile = self._contacts.pop(profile.name, None)
        self._contacts[profile.name] = profile
        return old_profile

    def remove_contact(self, name: str) -> Optional[ActorProfile]:
        return self._contacts.pop(name, None)

    def get_actor_profile(self, name: str) -> ActorProfile:
        try:
            return self._contacts[name]
        except KeyError as e:
            raise ActorNotFoundError(name) from e

    def all_actor_names(self) -> list[str]:
        return list(self._contacts.keys())

    def all_actors(self) -> Iterable[ActorProfile]:
        return self._contacts.values()


class Relationships(Locked, synchronize_all=True):

    def __init__(self, initial_relationships: Optional[Mapping[str, Iterable[RoleInstanceID]]] = None,
                 initial_relationship_links: Optional[Mapping[str, str]] = None):
        self._relationships: dict[str, set[RoleInstanceID]] = {}
        if initial_relationships:
            for name, instances in initial_relationships.items():
                self._relationships[name] = set(instances)
        self._relationship_links: dict[str, str] = {}
        if initial_relationship_links:
            for from_relationship_name, to_relationship_name in initial_relationship_links.items():
                self.link_relationship(from_relationship_name, to_relationship_name)

    def all_relationships(self) -> Mapping[str, frozenset[RoleInstanceID]]:
        return MappingProxyType({relationship_name: frozenset(instances)
                                 for relationship_name, instances in self._relationships.items()})

    def add_to_relationship(self, relationship_name: str, *instances: RoleInstanceID):
        if not instances:
            raise ValueError('role instances to add to relationship not provided')
        relationship = self._relationships.setdefault(relationship_name, set())
        relationship.update(instances)

    def remove_from_relationship(self, relationship_name: str, *instances: RoleInstanceID):
        if not instances:
            raise ValueError('role instances to remove from relationship not provided')
        if relationship_name in self._relationships:
            self._relationships[relationship_name].difference_update(instances)

    def get_relationship(self, relationship_name: str) -> Iterable[RoleInstanceID]:
        """ WARNING: The returned Iterable should only be iterated once. If you need multiple iterations, use the
        ``get_relationship_view()`` API. """
        if relationship_name in self._relationships:
            for instance in self._relationships[relationship_name]:
                yield instance

    def get_relationship_view(self, relationship_name: str) -> frozenset[RoleInstanceID]:
        return frozenset(self._relationships.get(relationship_name, ()))

    def get_relationship_unsafe(self, relationship_name: str) -> Set[RoleInstanceID]:
        """ Directly return the set of role instances that belong to the given relationship. The user should treat the
        returned set as read-only and make sure that concurrent access will not happen. """
        return self._relationships.get(relationship_name, frozenset())

    def instance_belongs_to_relationship(self, instance_name: RoleInstanceID, relationship_name: str) -> bool:
        if relationships := self._relationships.get(relationship_name, None):
            return instance_name in relationships
        else:
            return False

    def link_relationship(self, from_relationship_name: str, to_relationship_name: str):
        if self._relationships.get(from_relationship_name):     # and is not empty
            raise ValueError(f'cannot link relationship {from_relationship_name} to {to_relationship_name} '
                             f'because there are role instance(s) which belong to {from_relationship_name}')
        self._relationship_links[from_relationship_name] = to_relationship_name
        original_to = self._relationships.setdefault(to_relationship_name, set())
        self._relationships[from_relationship_name] = original_to


class Context(NamedTuple):

    start_time: float
    start_time_formatted: str
    workdir: str
    src: str
    seed: int

    contacts: Contacts
    relationships: Relationships
    handwaves: list[str]

    profile: ActorProfile

    @staticmethod
    def build(
            profile: ActorProfile, *,
            workdir: str = '.', src: Optional[str] = None, seed: int = -1,
            initial_relationships: Optional[Mapping[str, Iterable[RoleInstanceID]]] = None,
            initial_relationship_links: Optional[Mapping[str, str]] = None,
            initial_contacts: Optional[Iterable[ActorProfile]] = None,
            initial_handwaves: Optional[Iterable[str]] = None) -> 'Context':
        workdir_abs = os.path.abspath(workdir)
        src_abs = os.path.abspath(src) if src else workdir_abs
        os.chdir(workdir_abs)
        sys.path.append(src_abs)

        start_time = time.time()
        start_time_formatted = time.strftime('%Y-%m-%d-%H-%M-%S', time.localtime(start_time))
        if seed == -1:
            seed = random.randrange(sys.maxsize)
        random.seed(seed)

        contacts = Contacts(*initial_contacts or ())
        relationships = Relationships(initial_relationships, initial_relationship_links)

        return Context(
            start_time, start_time_formatted, workdir_abs, src_abs,
            seed, contacts, relationships, list(initial_handwaves or []), profile)

    def apply_general_template(self, template_str: str) -> str:
        import random
        from string import Template

        template = Template(template_str)
        return template.substitute(
            random=random.randint(1, 2147483647), timestamp=self.start_time, time=self.start_time_formatted,
            workdir=self.workdir, src=self.src, seed=self.seed)

    @staticmethod
    def active_context() -> 'Context':
        if _ACTIVE_CONTEXT is None:
            raise RuntimeError('no active context')
        return _ACTIVE_CONTEXT

    @staticmethod
    def set_active_context(ctx: 'Context'):
        global _ACTIVE_CONTEXT
        _ACTIVE_CONTEXT = ctx


_ACTIVE_CONTEXT: Optional[Context] = None
