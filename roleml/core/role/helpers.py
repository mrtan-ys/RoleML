from typing import Callable

from roleml.core.context import RoleInstanceID
from roleml.core.role.types import Args, Payloads

__all__ = ['require_relationship']


def require_relationship(name: str, message: str = ''):
    def decorate(handler: Callable):
        if hasattr(handler, '__self__'):
            raise TypeError('cannot decorate a bound method; use this decorator in role definition instead')

        def wrapped_message_handler(self, sender: RoleInstanceID, args: Args, payloads: Payloads):
            requirement: bool = self.ctx.relationships.instance_belongs_to_relationship(sender, name)
            self.require(requirement, message.format(sender=sender))
            return handler(self, sender, args, payloads)

        wrapped_message_handler._func_ = handler    # type: ignore  # additional attribute
        if hasattr(handler, 'properties'):
            # recover service/task/subscription annotation
            wrapped_message_handler.properties = handler.properties     # type: ignore
        return wrapped_message_handler
    return decorate
