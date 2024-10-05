from typing_extensions import override

from roleml.core.actor.default.managers.event import (
    EVENT_DISCONTINUING_UNIFIED_MESSAGE_CHANNEL,
    EVENT_SUBSCRIPTION_UNIFED_MESSAGING_CHANNEL,
    EVENT_UNIFIED_MESSAGING_CHANNEL,
    EVENT_UNSUBSCRIPTION_UNIFED_MESSAGING_CHANNEL,
    EventManager as DefaultEventManager,
)
from roleml.core.context import RoleInstanceID
from roleml.core.messaging.types import Args, Payloads, Tags, MyPayloads
from roleml.core.status import ExecutionTicket
from roleml.extensions.containerization.controller.managers.mixin import ContainerInvocationMixin
from roleml.shared.aop import aspect


@aspect
class EventManager(DefaultEventManager, ContainerInvocationMixin):

    @override
    def initialize(self):
        super().initialize()

    @override
    def _on_receive_event_discontinuing_message(self, sender: str, tags: Tags, _: Args, __: Payloads):
        try:
            instance_name = tags['instance_name']
            subscriber_instance_name = tags['subscriber_instance_name']
        except KeyError:
            raise AssertionError('incomplete event discontinuing info')

        if not self._is_role_containerized(subscriber_instance_name):
            super()._on_receive_event_discontinuing_message(sender, tags, _, __)
        else:
            ticket = self._acquire_execution(subscriber_instance_name)
            self.thread_manager.add_threaded_task(
                self._forward_discontinuing_message_to_container,
                (sender, instance_name, subscriber_instance_name, ticket),
            )

    def _forward_discontinuing_message_to_container(
        self,
        source_actor_name: str,
        source_instance_name: str,
        target_instance_name: str,
        ticket: ExecutionTicket,
    ):
        try:
            self._invoke_container(
                target_instance_name,
                EVENT_DISCONTINUING_UNIFIED_MESSAGE_CHANNEL,
                tags={
                    "instance_name": source_instance_name,
                    "actor_name": source_actor_name,  # used for containerized role to recognize the actual sender
                },
            )
        finally:
            ticket.stop()

    # region emit

    @override
    def _on_receive_event_message(self, sender: str, tags: Tags, args: Args, payloads: Payloads):
        try:
            target_subscriber_instance_name = tags['subscriber_instance_name']
        except KeyError:
            raise AssertionError('incomplete event trigger info')

        if not self._is_role_containerized(target_subscriber_instance_name):
            super()._on_receive_event_message(sender, tags, args, payloads)
        else:
            ticket = self._acquire_execution(target_subscriber_instance_name)
            self.thread_manager.add_threaded_task(
                self._forward_event_message_to_container,
                (sender, tags, args, payloads, ticket),
            )

    def _forward_event_message_to_container(
        self,
        sender: str,
        tags: Tags,
        args: Args,
        payloads: Payloads,
        ticket: ExecutionTicket,
    ):
        target_subscriber_instance_name = tags["subscriber_instance_name"]
        try:
            tags = {
                **tags,
                # the actor of the source instance.
                # used for containerized role to recognize the actual sender.
                "source_actor_name": sender,
            }
            self._invoke_container(
                target_subscriber_instance_name,
                EVENT_UNIFIED_MESSAGING_CHANNEL,
                tags,
                args,
                payloads,
            )
        finally:
            ticket.stop()

    # endregion emit

    # region subscription/unsubscription

    @override
    def _on_receive_event_subscription_message(self, sender: str, tags: Tags, args: Args, _: Payloads):
        try:
            source_instance_name: str = tags['source_instance_name']
        except KeyError:
            raise AssertionError('incomplete tags for event subscription')

        if not self._is_role_containerized(source_instance_name):
            return super()._on_receive_event_subscription_message(sender, tags, args, _)
        else:
            with self._execute_environment_for_role(source_instance_name, None):
                tags = {
                    **tags,
                    # the actor of the subscriber instance.
                    # used for containerized role to recognize the actual sender.
                    'subscriber_actor_name': sender,
                }
                ret: int = self._invoke_container(
                    source_instance_name, EVENT_SUBSCRIPTION_UNIFED_MESSAGING_CHANNEL, 
                    tags, args, _)
                return ret

    @override
    def _on_receive_event_unsubscription_message(self, sender: str, tags: Tags, _: Args, __: Payloads):
        try:
            source_instance_name: str = tags['source_instance_name']
        except KeyError as e:
            raise AssertionError('incomplete tags for event subscription') from e

        if not self._is_role_containerized(source_instance_name):
            return super()._on_receive_event_unsubscription_message(sender, tags, _, __)
        else:
            with self._execute_environment_for_role(source_instance_name, None):
                tags = {
                    **tags,
                    # the actor of the subscriber instance.
                    # used for containerized role to recognize the actual sender.
                    'subscriber_actor_name': sender,
                }
                ret: bool = self._invoke_container(
                    source_instance_name,
                    EVENT_UNSUBSCRIPTION_UNIFED_MESSAGING_CHANNEL, tags)
                return ret

    # endregion subscription/unsubscription

    def update_instance_id(
        self, instance_id: RoleInstanceID, new_instance_id: RoleInstanceID
    ):
        with self.event_lock.write_lock():
            for event_channels in self.events.values():
                for event_info in event_channels.values():
                    if instance_id in event_info.remote_subscribers:
                        sub_info = event_info.remote_subscribers.pop(instance_id)
                        event_info.remote_subscribers[new_instance_id] = sub_info

        with self.subscription_lock.write_lock():
            if instance_id in self.subscriptions_by_source_channel:
                sub_info = self.subscriptions_by_source_channel.pop(instance_id)
                self.subscriptions_by_source_channel[new_instance_id] = sub_info
