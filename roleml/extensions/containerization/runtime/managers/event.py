from typing import Any, Callable, Optional
from typing_extensions import override

from roleml.core.actor.default.managers.event import EventManager as DefaultEventManager
from roleml.core.actor.manager.helpers import parse_conditions
from roleml.core.context import RoleInstanceID
from roleml.core.messaging.types import Args, Payloads, Tags
from roleml.core.role.exceptions import NoSuchRoleError
from roleml.core.role.types import EventSubscriptionMode
from roleml.core.status import Status
from roleml.extensions.containerization.runtime.managers.mixin import InterContainerMixin
from roleml.shared.aop import aspect


@aspect
class EventManager(DefaultEventManager, InterContainerMixin):

    @override
    def initialize(self):
        super().initialize()

    @override
    def _is_local_instance(self, instance_name: RoleInstanceID) -> bool:
        return instance_name.instance_name == "__this"

    @override
    def _on_role_status_starting(self, instance_name: str, old_status: Status):
        assert old_status == Status.DECLARED
        with self.subscription_listeners_lock, self.relationships:
            # lock status of relationships when performing auto subscription for the first time
            pending_listeners = self.pending_listeners.pop(instance_name, {})
            for relationship_name, listeners in pending_listeners.items():
                for listener in listeners.values():
                    properties = listener.properties
                    self.subscription_listeners[relationship_name][instance_name][properties.channel_name] = listener
                    if current_instances := self.relationships.get_relationship_unsafe(relationship_name):
                        self._auto_subscribe_impl(instance_name, listener, current_instances)
                    elif relationship_name in self.events:
                        try:
                            self._subscribe_local(
                                instance_name, relationship_name, properties.channel_name, listener.handler,
                                parsed_conditions=parse_conditions(properties.conditions), mode=properties.mode)
                        except Exception:   # noqa
                            pass    # channel not found, OK
                    else:
                        # implicit relationship is not supported in containerized mode
                        self.logger.error(
                            f'auto-subscribe {instance_name} to r/{relationship_name}/{properties.channel_name} '
                            f'has no relationship. Implicit relationship is not supported in containerized mode')
                        raise NoSuchRoleError(f"no such relationship: {relationship_name}")
                        # self._auto_subscribe_impl(
                        #     instance_name, listener, [RoleInstanceID(self.context.profile.name, relationship_name)])

    @override
    def _on_receive_event_discontinuing_message(self, sender: str, tags: Tags, _: Args, __: Payloads):
        try:
            actor_name = tags['actor_name']
        except KeyError:
            # raise AssertionError('incomplete event discontinuing info: missing actor_name')
            actor_name = sender
        return super()._on_receive_event_discontinuing_message(actor_name, tags, _, __)

    # region emit

    @override
    def _on_receive_event_message_impl(self, sender: str, tags: Tags, args: Args, payloads: Payloads):
        try:
            source_actor_name = tags['source_actor_name']
        except KeyError:
            # raise AssertionError('incomplete event trigger info: missing source_actor_name')
            source_actor_name = sender
        return super()._on_receive_event_message_impl(source_actor_name, tags, args, payloads)

    # endregion emit

    # region subscription/unsubscription

    @override
    def subscribe(self, instance_name: str, target: RoleInstanceID, channel_name: str,
                  handler: Callable[[RoleInstanceID, Args, Payloads], Any],
                  *, conditions: Optional[dict[str, Any]] = None, mode: EventSubscriptionMode = 'forever'):
        target = self._convert_target_actor_name(target)
        return super().subscribe(instance_name, target, channel_name, handler, conditions=conditions, mode=mode)

    @override
    def _on_receive_event_subscription_message(self, sender: str, tags: Tags, args: Args, _: Payloads):
        try:
            subscriber_actor_name: str = tags['subscriber_actor_name']
        except KeyError:
            # raise AssertionError('incomplete tags for event subscription: missing subscriber_actor_name')
            subscriber_actor_name = sender
        return super()._on_receive_event_subscription_message(subscriber_actor_name, tags, args, _)

    @override
    def unsubscribe(self, instance_name: str, target: RoleInstanceID, channel_name: str):
        target = self._convert_target_actor_name(target)
        return super().unsubscribe(instance_name, target, channel_name)

    @override
    def _on_receive_event_unsubscription_message(self, sender: str, tags: Tags, _: Args, __: Payloads):
        try:
            subscriber_actor_name: str = tags['subscriber_actor_name']
        except KeyError as e:
            # raise AssertionError('incomplete tags for event subscription: missing subscriber_actor_name')
            subscriber_actor_name = sender
        return super()._on_receive_event_unsubscription_message(subscriber_actor_name, tags, _, __)

    # endregion subscription/unsubscription

    def update_instance_id(
        self, instance_id: RoleInstanceID, new_instance_id: RoleInstanceID
    ):
        with self.event_lock.write_lock():
            # shallow copy, avoid modifying the original dict while other thread is iterating
            self.events = self.events.copy()
            for event_channels in self.events.values():
                for event_info in event_channels.values():
                    if instance_id in event_info.remote_subscribers:
                        # shallow copy
                        event_info.remote_subscribers = event_info.remote_subscribers.copy()
                        sub_info = event_info.remote_subscribers.pop(instance_id)
                        event_info.remote_subscribers[new_instance_id] = sub_info

        with self.subscription_lock.write_lock():
            # shallow copy
            self.subscriptions_by_source_channel = self.subscriptions_by_source_channel.copy()
            if instance_id in self.subscriptions_by_source_channel:
                sub_info = self.subscriptions_by_source_channel.pop(instance_id)
                self.subscriptions_by_source_channel[new_instance_id] = sub_info
