""" One-line import of common things: ``import roleml.essentials as rml`` """
from roleml.core.actor.base import BaseActor
from roleml.core.actor.default.bootstrap import ActorBuilder
from roleml.core.actor.default.impl import Actor
from roleml.core.builders.actor import LogConsoleType, ActorBootstrapSpec
from roleml.core.builders.element import ElementImplementationSpec, \
    loader_methods, serializer_methods, initializer_methods, unloader_methods
from roleml.core.builders.role import RoleDescriptor, RoleSpec
from roleml.core.context import RoleInstanceID, RoleInstanceIDTuple
from roleml.core.role.base import Role as Role
from roleml.core.role.channels import Service, Task, Event, EventHandler, Alias, attribute
from roleml.core.role.elements import Element
from roleml.core.role.types import Message, Args, Payloads, MyArgs, MyPayloads, \
    TaskInvocation, EventSubscriptionMode, PluginAttribute

__all__ = [
    'BaseActor',
    'ActorBuilder', 'Actor',
    'ActorBootstrapSpec', 'LogConsoleType',
    'ElementImplementationSpec', 'loader_methods', 'serializer_methods', 'initializer_methods', 'unloader_methods',
    'RoleDescriptor', 'RoleSpec',
    'RoleInstanceID', 'RoleInstanceIDTuple',
    'Role',
    'Service', 'Task', 'Event', 'EventHandler', 'Alias', 'attribute',
    'Element',
    'Message', 'Args', 'Payloads', 'MyArgs', 'MyPayloads', 'TaskInvocation', 'EventSubscriptionMode', 'PluginAttribute',
]
