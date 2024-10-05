import logging
from typing import Any, Callable, ClassVar, Iterable, Mapping, Optional, Union, TYPE_CHECKING

from roleml.core.actor.group.helpers import ErrorHandlingStrategy
from roleml.core.context import ActorProfile, RoleInstanceID, Context
from roleml.core.role.channels import EventHandlerProperties, Event, ChannelType, ServiceTaskHandlerProperties
from roleml.core.role.elements import Element
from roleml.core.role.exceptions import CallerError
from roleml.core.role.naming import to_standardized_name
from roleml.core.role.types import Args, Payloads, Message, TaskInvocation, EventSubscriptionMode, PluginAttribute

if TYPE_CHECKING:
    from roleml.core.actor.base import BaseActor

__all__ = ['Role']


class Role:

    # e.g.
    # aggregation_completed = Event()   # use default name, to be filled by actor on attachment
    # model = Element(...)

    services: ClassVar[dict[str, str]]  # channel_name => attribute_name
    tasks: ClassVar[dict[str, str]]     # channel_name => attribute_name
    events: ClassVar[dict[str, str]]    # channel_name => attribute_name
    subscriptions: ClassVar[set[str]]   # attribute_names

    elements: ClassVar[dict[str, str]]  # element_name => attribute_name

    plugin_attributes: dict[str, list[str]]     # plugin_name => attribute_names

    def __init__(self, **kwargs):
        self.name: str = ""                 # to be filled by actor
        self._base: 'BaseActor' = None      # type: ignore  # to be filled by actor
        self._ctx: Context = None           # type: ignore  # to be filled by actor
        self.logger = logging.getLogger()   # to be reset when attached to actor

    def __init_subclass__(cls, **kwargs):
        # inherit by creating a copy from parent
        cls.services = getattr(cls, 'services', {}).copy()
        cls.tasks = getattr(cls, 'tasks', {}).copy()
        cls.events = getattr(cls, 'events', {}).copy()
        cls.subscriptions = getattr(cls, 'subscriptions', set()).copy()
        cls.elements = getattr(cls, 'elements', {}).copy()
        cls.plugin_attributes = getattr(cls, 'plugin_attributes', {}).copy()
        for attr_name, attr in cls.__dict__.items():
            if isinstance(attr, Event):     # is an event channel
                standardized_name = to_standardized_name(getattr(attr, 'channel_name', attr_name) or attr_name)
                attr.channel_name = standardized_name
                cls.events[standardized_name] = attr_name
            elif properties := getattr(attr, 'properties', None):                   # is a handler of
                if hasattr(properties, 'conditions'):                               # an event subscription
                    assert isinstance(properties, EventHandlerProperties)
                    properties.channel_name = to_standardized_name(properties.channel_name)
                    cls.subscriptions.add(attr_name)
                elif channel_type := getattr(properties, 'channel_type', None):     # a service or task channel
                    assert isinstance(properties, ServiceTaskHandlerProperties)
                    standardized_name = to_standardized_name(properties.channel_name)
                    properties.channel_name = standardized_name
                    if channel_type == ChannelType.SERVICE:
                        cls.services[standardized_name] = attr_name
                    elif channel_type == ChannelType.TASK:
                        cls.tasks[standardized_name] = attr_name
                    else:
                        assert False
            elif isinstance(attr, Element):
                cls.elements[to_standardized_name(attr_name)] = attr_name
            elif isinstance(attr, PluginAttribute):
                plugin_name = attr.__class__.PLUGIN_NAME
                plugin_attrs = cls.plugin_attributes.setdefault(plugin_name, [])
                plugin_attrs.append(attr_name)

    @property
    def base(self) -> 'BaseActor':
        if self._base is None:
            raise RuntimeError('role not initialized')
        return self._base

    @property
    def ctx(self) -> Context:
        return self.base.ctx

    @property
    def profile(self) -> ActorProfile:
        return self.base.profile

    @property
    def id(self) -> RoleInstanceID:
        return RoleInstanceID(self.base.profile.name, self.name)

    def attach(self, name: str, base: 'BaseActor'):
        """ Internal API; do not call this manually in user code. """
        if self._base is not None:
            raise RuntimeError('role already initialized')
        self.name = name
        self._base = base
        self.logger = logging.getLogger(f'roleml.roles.{name}')

    def call(self, target: Union[str, RoleInstanceID], channel_name: str,
             args: Optional[Args] = None, payloads: Optional[Payloads] = None, *, message: Optional[Message] = None
             ) -> Any:
        if message is None:
            message = Message(args or {}, payloads or {})
        return self.base.call(self.name, target, to_standardized_name(channel_name), message)

    def call_group(
            self, group: Iterable[RoleInstanceID], channel_name: str,
            args: Optional[Args] = None, payloads: Optional[Payloads] = None, *,
            message_map: Optional[Mapping[RoleInstanceID, Message]] = None, 
            message: Optional[Message] = None, messages: Optional[Iterable[Message]] = None,
            on_result: Optional[Callable[[RoleInstanceID, Any], Any]] = None,
            on_error: ErrorHandlingStrategy = ErrorHandlingStrategy.RAISE_FIRST
    ) -> Iterable[tuple[RoleInstanceID, Any]]:
        if message is None:
            message = Message(args or {}, payloads or {})
        return self.base.call_group(self.name, group, to_standardized_name(channel_name),
                                    message=message, message_map=message_map, messages=messages,
                                    on_result=on_result, on_error=on_error)

    def call_task(self, target: Union[str, RoleInstanceID], channel_name: str,
                  args: Optional[Args] = None, payloads: Optional[Payloads] = None, *, message: Optional[Message] = None
                  ) -> TaskInvocation:
        if message is None:
            message = Message(args or {}, payloads or {})
        return self.base.call_task(self.name, target, to_standardized_name(channel_name), message)

    def call_task_group(
            self, group: Iterable[RoleInstanceID], channel_name: str,
            args: Optional[Args] = None, payloads: Optional[Payloads] = None, *,
            message_map: Optional[Mapping[RoleInstanceID, Message]] = None, 
            message: Optional[Message] = None, messages: Optional[Iterable[Message]] = None,
            on_call_error: ErrorHandlingStrategy = ErrorHandlingStrategy.RAISE_FIRST,
            on_result: Optional[Callable[[RoleInstanceID, TaskInvocation], Any]] = None):
        if message is None:
            message = Message(args or {}, payloads or {})
        self.base.call_task_group(self.name, group, to_standardized_name(channel_name),
                                  message=message, message_map=message_map, messages=messages,
                                  on_call_error=on_call_error, on_result=on_result)
    
    def subscribe(self, target: RoleInstanceID, channel_name: str,
                  handler: Callable[[RoleInstanceID, Args, Payloads], Any], *,
                  conditions: Optional[dict[str, Any]] = None, mode: EventSubscriptionMode = 'forever'):
        self.base.subscribe(self.name, target, channel_name, handler, conditions=conditions, mode=mode)

    def unsubscribe(self, target: RoleInstanceID, channel_name: str):
        self.base.unsubscribe(self.name, target, channel_name)

    def require(self, condition, message: str = 'handler assertion failed'):    # noqa: static
        if not condition:
            raise CallerError(message)
