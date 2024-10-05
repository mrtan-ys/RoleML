from dataclasses import dataclass
from enum import auto, Enum
from functools import wraps
from typing import Any, Callable, Optional, Protocol, Union, TYPE_CHECKING

from roleml.core.context import RoleInstanceID
from roleml.core.role.types import Args, Payloads, Message, EventSubscriptionMode

if TYPE_CHECKING:
    from roleml.core.role.base import Role


class ChannelType(Enum):
    SERVICE = auto()
    TASK = auto()
    EVENT = auto()


class HandlerDecorator:

    def __init__(self, expand: bool):
        self.expand = expand

    def __call__(self, handler: Callable[..., Any]):
        if hasattr(handler, '__self__'):
            raise TypeError('cannot decorate a bound method; use this decorator in role definition instead')
        if self.expand:
            @wraps(handler)
            def handler_wrapped(self_: 'Role', caller: RoleInstanceID, args: Args, payloads: Payloads):
                return handler(self_, caller, **args, **payloads)
            return handler_wrapped
        else:
            return handler


@dataclass
class ServiceTaskHandlerProperties:
    channel_name: str
    channel_type: ChannelType


class ServiceTaskHandlerDecorator(HandlerDecorator):

    def __init__(self, channel_name: Optional[str], channel_type: ChannelType, expand: bool):
        super().__init__(expand)
        self.channel_name = channel_name
        self.channel_type = channel_type

    def __call__(self, handler: Callable[..., Any]):
        handler_wrapped = super().__call__(handler)
        handler_wrapped.properties = ServiceTaskHandlerProperties(  # type: ignore
            self.channel_name or handler.__name__,  # will be converted to standardized name in Role
            self.channel_type)
        return handler_wrapped


@dataclass
class EventHandlerProperties:
    channel_name: str
    relationship: str
    extra_filter: Callable[[RoleInstanceID], bool]
    conditions: dict[str, Any]
    mode: EventSubscriptionMode


class EventHandlerDecorator(HandlerDecorator):

    def __init__(self, channel_name: str, expand: bool, conditions: dict[str, Any], mode: EventSubscriptionMode,
                 relationship: str, extra_filter: Callable[[RoleInstanceID], bool]):
        super().__init__(expand)
        self.channel_name = channel_name
        self.conditions = conditions
        self.mode: EventSubscriptionMode = mode
        self.relationship, self.extra_filter = relationship, extra_filter

    def __call__(self, handler: Callable):
        handler_wrapped = super().__call__(handler)
        handler_wrapped.properties = EventHandlerProperties(    # type: ignore
            self.channel_name or handler.__name__,  # will be converted to standardized name in Role
            self.relationship, self.extra_filter, self.conditions, self.mode)
        return handler_wrapped


# region user APIs

class Event:

    class EmitImplementor(Protocol):
        def emit(self, instance_name: str, channel_name: str, message: Message): ...

    __slots__ = ('channel_name', 'role_name', 'base')

    def __init__(self, channel_name: Optional[str] = None):
        self.channel_name: str = channel_name       # type: ignore  # to be filled by manager of actor if None
        self.role_name: str = ""                    # to be filled by manager of actor
        self.base: 'Event.EmitImplementor' = None   # type: ignore  # to be filled by manager of actor

    def emit(self, args: Optional[Args] = None, payloads: Optional[Payloads] = None,
             *, message: Optional[Message] = None):
        if not self.base:    # manager check bypassing role
            raise RuntimeError(f'event channel {self.channel_name} is not contained in a context')
        if message is None:
            message = Message(args or {}, payloads or {})
        self.base.emit(self.role_name, self.channel_name, message)


# noinspection PyPep8Naming
def Service(channel_name: Union[str, None, Callable] = None, *, expand: bool = False) -> Any:
    # return Any to prevent type errors in roles
    if isinstance(channel_name, str) or channel_name is None:
        # calling as @Service()
        return ServiceTaskHandlerDecorator(channel_name, ChannelType.SERVICE, expand)
    else:
        # calling as @Service without parens
        assert callable(channel_name)
        return ServiceTaskHandlerDecorator(None, ChannelType.SERVICE, False)(channel_name)


# noinspection PyPep8Naming
def Task(channel_name: Union[str, None, Callable] = None, *, expand: bool = False) -> Any:
    # return Any to prevent type errors in roles
    if isinstance(channel_name, str) or channel_name is None:
        # calling as @Task()
        return ServiceTaskHandlerDecorator(channel_name, ChannelType.TASK, expand)
    else:
        # calling as @Task without parens
        assert callable(channel_name)
        return ServiceTaskHandlerDecorator(None, ChannelType.TASK, False)(channel_name)


# noinspection PyPep8Naming
def EventHandler(relationship: str, channel_name: str, *, expand: bool = False,
                 conditions: Optional[dict[str, Any]] = None, mode: EventSubscriptionMode = 'forever',
                 extra_filter: Callable[[RoleInstanceID], bool] = lambda instance: True):
    return EventHandlerDecorator(channel_name, expand, conditions or {}, mode, relationship, extra_filter)


# noinspection PyPep8Naming
class attribute:

    __slots__ = ('name', )

    def __init__(self, name: str):
        self.name = name

# endregion
