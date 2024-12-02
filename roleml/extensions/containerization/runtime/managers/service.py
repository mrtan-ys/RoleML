from typing import Any, Union
from typing_extensions import override

from roleml.core.actor.default.managers.service import ServiceManager as DefaultServiceManager
from roleml.core.actor.helpers import PayloadsPickledMessage
from roleml.core.context import RoleInstanceID
from roleml.core.messaging.types import Args, Payloads, Tags
from roleml.core.role.types import Message
from roleml.extensions.containerization.runtime.managers.mixin import InterContainerMixin


class ServiceManager(DefaultServiceManager, InterContainerMixin):

    @override
    def initialize(self):
        super().initialize()

    @override
    def _is_local_instance(self, instance_name: RoleInstanceID) -> bool:
        return instance_name.instance_name == "__this"

    @override
    def _on_receive_service_message(self, sender: str, tags: Tags, args: Args, payloads: Payloads):
        try:
            from_actor_name = tags['from_actor_name']
        except KeyError:
            # raise AssertionError('unspecified from actor name')
            from_actor_name = sender
        return super()._on_receive_service_message(from_actor_name, tags, args, payloads)

    @override
    def call(self, instance_name: str, target: RoleInstanceID, channel_name: str,
             message: Union[Message, PayloadsPickledMessage]) -> Any:
        target = self._convert_target_actor_name(target)
        return super().call(instance_name, target, channel_name, message)