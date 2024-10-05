""" One-line import of common things: ``import roleml.essentials as rml`` """
from roleml.core.actor.base import BaseActor
from roleml.core.actor.default.bootstrap import ActorBuilder
from roleml.core.actor.default.impl import Actor
from roleml.core.builders.actor import LogConsoleType, ActorBootstrapSpec
from roleml.core.builders.element import ElementImplementationSpec, ParsedElementImplementationSpec
from roleml.core.builders.role import RoleDescriptor, RoleSpec
from roleml.core.context import RoleInstanceID, RoleInstanceIDTuple
from roleml.core.role.base import Role as Role
from roleml.core.role.channels import Service, Task, Event, EventHandler, attribute
from roleml.core.role.elements import Element, Factory, ConstructStrategy, InitializeStrategy
from roleml.core.role.types import Message, Args, Payloads, MyArgs, MyPayloads, \
    TaskInvocation, EventSubscriptionMode, PluginAttribute

__all__ = [
    'BaseActor',
    'ActorBuilder', 'Actor',
    'ActorBootstrapSpec', 'LogConsoleType',
    'ElementImplementationSpec', 'ParsedElementImplementationSpec',
    'RoleDescriptor', 'RoleSpec',
    'RoleInstanceID', 'RoleInstanceIDTuple',
    'Role',
    'Service', 'Task', 'Event', 'EventHandler', 'attribute',
    'Element', 'Factory', 'ConstructStrategy', 'InitializeStrategy',
    'Message', 'Args', 'Payloads', 'MyArgs', 'MyPayloads', 'TaskInvocation', 'EventSubscriptionMode', 'PluginAttribute',
]
