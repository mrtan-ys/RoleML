import logging
from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass, field
from threading import RLock
from typing import Any, Callable, Iterable, Mapping, NamedTuple, Optional, Union

from fasteners import ReaderWriterLock

from roleml.core.actor.default.managers.channels import ChannelCallManagerMixin
from roleml.core.actor.manager import BaseEventManager
from roleml.core.actor.manager.helpers import check_conditions, parse_conditions, EventConditionChecker
from roleml.core.context import RoleInstanceID, Relationships
from roleml.core.messaging.exceptions import InvocationAbortError, InvocationRefusedError
from roleml.core.messaging.types import Args, Payloads, Tags, MyArgs, MyPayloads
from roleml.core.role.base import Role
from roleml.core.role.channels import Event, EventHandlerProperties, attribute as Attribute     # noqa: naming
from roleml.core.role.exceptions import ChannelNotFoundError, NoSuchEventError, CallerError, HandlerError
from roleml.core.role.types import EventSubscriptionMode, Message
from roleml.core.status import Status
from roleml.shared.aop import aspect, after, InvocationActivity
from roleml.shared.types import LOG_LEVEL_INTERNAL as INTERNAL


class EventRemoteSubscriberInfo(NamedTuple):
    mode: EventSubscriptionMode
    conditions: Iterable[EventConditionChecker]     # parsed conditions
    subscription_id: str


class EventLocalSubscriberInfo(NamedTuple):
    mode: EventSubscriptionMode
    conditions: Iterable[EventConditionChecker]     # parsed conditions
    handler: Callable[[RoleInstanceID, Args, Payloads], Any]
    sequence: int = -1      # valid only when the event source is not local


# NamedTuple inheritance not working as expected, otherwise we can just let
# both EventLocalSubscriberInfo and EventRemoteSubscriberInfo inherit another NT
# This blog might have provided a solution for this, but is out of scope of RoleML:
# http://zecong.hu/2019/08/10/inheritance-for-namedtuples
EventSubscriberInfo = Union[EventRemoteSubscriberInfo, EventLocalSubscriberInfo]


@dataclass
class EventInfo:
    """ Information about subscribers of a given event channel. Stored at event source side. """
    lock: RLock = field(default_factory=RLock)
    # subscriber instance => Info
    local_subscribers: dict[str, EventLocalSubscriberInfo] = field(default_factory=dict)
    # subscriber instance => Info
    remote_subscribers: dict[RoleInstanceID, EventRemoteSubscriberInfo] = field(default_factory=dict)
    # sequence number to manage which subscribers to send an event message to
    sequence: int = 0


@dataclass
class EventConveyTable:
    """ Information about local subscription of a given remote event channel. """
    lock: RLock = field(default_factory=RLock)
    # subscriber instance => info
    subscribers: dict[str, EventLocalSubscriberInfo] = field(default_factory=dict)


class EventSubscriptionListener(NamedTuple):
    handler: Callable[[RoleInstanceID, Args, Payloads], Any]
    properties: EventHandlerProperties


EVENT_UNIFIED_MESSAGING_CHANNEL = 'EVENT'
EVENT_SUBSCRIPTION_UNIFED_MESSAGING_CHANNEL = 'EVENT_SUB'
EVENT_UNSUBSCRIPTION_UNIFED_MESSAGING_CHANNEL = 'EVENT_UNSUB'
EVENT_DISCONTINUING_UNIFIED_MESSAGE_CHANNEL = 'EVENT_DISCONTINUE'


@aspect
class EventManager(BaseEventManager, ChannelCallManagerMixin):

    # locally registered event channels
    events: dict[str, dict[str, EventInfo]]     # instance name => (channel name => Info)
    event_lock: ReaderWriterLock

    # source instance => (source channel => conveyer); used in remote
    subscriptions_by_source_channel: defaultdict[RoleInstanceID, dict[str, EventConveyTable]]
    subscription_lock: ReaderWriterLock

    # relationship name => (subscriber instance name => (channel name => listener))
    subscription_listeners: defaultdict[str, defaultdict[str, dict[str, EventSubscriptionListener]]]
    # subscriber instance name => (relationship name => (channel name => listener))
    # auto subscription will not happen until the role is about to start
    pending_listeners: defaultdict[str, defaultdict[str, dict[str, EventSubscriptionListener]]]
    # mutual exclusive assess control for both `subscription_listeners` and `pending_listeners`
    subscription_listeners_lock: RLock

    relationships: Relationships

    def initialize(self):
        self.events = {}
        self.event_lock = ReaderWriterLock()
        self.subscriptions_by_source_channel = defaultdict(dict)
        self.subscription_lock = ReaderWriterLock()
        self.subscription_listeners = defaultdict(lambda: defaultdict(dict))
        self.pending_listeners = defaultdict(lambda: defaultdict(dict))
        self.subscription_listeners_lock = RLock()
        self.relationships = self.context.relationships
        self.logger = logging.getLogger('roleml.managers.event')
        self.procedure_provider.add_procedure(
            EVENT_UNIFIED_MESSAGING_CHANNEL, self._on_receive_event_message)
        self.procedure_provider.add_procedure(
            EVENT_SUBSCRIPTION_UNIFED_MESSAGING_CHANNEL, self._on_receive_event_subscription_message)
        self.procedure_provider.add_procedure(
            EVENT_UNSUBSCRIPTION_UNIFED_MESSAGING_CHANNEL, self._on_receive_event_unsubscription_message)
        self.procedure_provider.add_procedure(
            EVENT_DISCONTINUING_UNIFIED_MESSAGE_CHANNEL, self._on_receive_event_discontinuing_message)
        self.role_status_manager.add_callback(Status.STARTING, self._on_role_status_starting)
        self.role_status_manager.add_callback(Status.FINALIZING, self._on_role_status_finalizing)

    def add_role(self, role: Role):
        with self.event_lock.write_lock():
            # register declared event channels
            events = self.events[role.name] = {}
            for channel_name, attribute_name in role.events.items():
                events[channel_name] = EventInfo()
                ev = Event(channel_name)
                ev.base = self
                ev.role_name = role.name
                setattr(role, attribute_name, ev)
        with self.subscription_listeners_lock:
            # pre-register automatic subscriptions
            for attribute_name in role.subscriptions:
                template = getattr(role.__class__, attribute_name)
                listener = EventSubscriptionListener(getattr(role, attribute_name), template.properties)
                conditions = listener.properties.conditions = deepcopy(listener.properties.conditions)
                try:
                    for key in conditions:
                        val = conditions[key]
                        if isinstance(val, Attribute):
                            conditions[key] = getattr(role, val.name)
                except AttributeError as e:
                    self.logger.error(f'cannot register event handler for '
                                      f'{listener.properties.relationship}/{listener.properties.channel_name}: {e}')
                else:
                    self.pending_listeners \
                        [role.name][listener.properties.relationship][listener.properties.channel_name] = listener
            # treat the role name as a relationship name only when there is no matching role instance belonging to the
            # corresponding relationship, and handle automatic subscription to this role (since adding a role does not
            # trigger relationship update)
            if role.name in self.subscription_listeners:
                with self.relationships:
                    if not self.relationships.get_relationship_unsafe(role.name):
                        source_id = RoleInstanceID(self.context.profile.name, role.name)
                        for subscriber_instance_name, listeners in self.subscription_listeners[role.name].items():
                            for listener in listeners.values():
                                self._auto_subscribe_impl(subscriber_instance_name, listener, [source_id])
                                self.logger.info(f'automatic event subscription of r/{role.name} from local role '
                                                 f'instance {subscriber_instance_name} given the new role {role.name}')

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
                            self.logger.info(
                                f'automatic event subscription of r/{relationship_name}/{properties.channel_name} '
                                f'subscribes to local role instance {relationship_name}')
                        except Exception:   # noqa
                            pass    # channel not found, OK

    def _on_role_status_finalizing(self, instance_name: str, _):
        # remove automatic subscriptions
        with self.subscription_listeners_lock:
            self.subscription_listeners.pop(instance_name, None)
            self.pending_listeners.pop(instance_name, None)
        self.logger.info(f'automatic subscription listeners for role {instance_name} removed')
        notified_actors: set[str] = set()

        def notify_actor_at_most_once(actor_name: str, subscriber_instance_name: str):
            if actor_name in notified_actors:
                return
            tags = {
                # the terminating role instance
                'instance_name': instance_name,
                # remote instance who subscribed to the terminating role instance
                'subscriber_instance_name': subscriber_instance_name,
            }
            try:
                self.procedure_invoker.invoke_procedure(
                    actor_name, EVENT_DISCONTINUING_UNIFIED_MESSAGE_CHANNEL, tags=tags)
            except Exception:   # noqa: using Logger.exception()
                self.logger.debug(
                    f'failed to send event discontinuation msg to {actor_name}; '
                    f'it is possible that the target actor is already down')
            finally:
                notified_actors.add(actor_name)

        # notify other actors who provide event sources and remove registrations locally
        with self.subscription_lock.write_lock():
            self.subscriptions_by_source_channel.pop(RoleInstanceID(self.context.profile.name, instance_name), None)
            cleanup_out: list[RoleInstanceID] = []
            for source_instance_id, sbs in self.subscriptions_by_source_channel.items():
                cleanup_in: list[str] = []
                for source_channel_name, convey_table in sbs.items():
                    if instance_name in convey_table.subscribers:
                        notify_actor_at_most_once(source_instance_id.actor_name, source_instance_id.instance_name)
                        del convey_table.subscribers[instance_name]
                        if not convey_table.subscribers:
                            cleanup_in.append(source_channel_name)
                for source_channel_name in cleanup_in:
                    del sbs[source_channel_name]
                if not sbs:
                    cleanup_out.append(source_instance_id)
            for source_instance_id in cleanup_out:
                del self.subscriptions_by_source_channel[source_instance_id]
        self.logger.info(f'current subscriptions of role {instance_name} removed')

        # notify other actors who have subscribed to the terminating role instance and remove registrations locally
        with self.event_lock.write_lock():
            events = self.events.pop(instance_name)
            for channel_name, info in events.items():
                for subscriber_instance_id in info.remote_subscribers.keys():
                    notify_actor_at_most_once(subscriber_instance_id.actor_name, subscriber_instance_id.instance_name)
        self.logger.info(f'events of role {instance_name} removed')

    def _on_receive_event_discontinuing_message(self, sender: str, tags: Tags, _: Args, __: Payloads):
        try:
            instance_name = tags['instance_name']
        except KeyError:
            raise AssertionError('incomplete event discontinuing info')
        else:
            self.thread_manager.add_threaded_task(
                self._on_receive_event_discontinuing_message_impl, (sender, instance_name))

    def _on_receive_event_discontinuing_message_impl(self, source_actor_name: str, source_instance_name: str):
        with self.subscription_lock.write_lock():
            self.subscriptions_by_source_channel.pop(RoleInstanceID(source_actor_name, source_instance_name))

    # region emit

    def emit(self, instance_name: str, channel_name: str, message: Message):
        local_channel_name = f'{instance_name}/{channel_name}'
        with self._execute_environment_for_role(instance_name, None):
            try:
                with self.event_lock.read_lock():
                    info = self.events[instance_name][channel_name]
            except KeyError:
                raise NoSuchEventError(f'{local_channel_name}') from None
            else:
                with info.lock:
                    self.logger.debug(f'new event in channel {local_channel_name}, args = {message.args}')
                    self.logger.log(INTERNAL, f'current sequence of channel {local_channel_name} is {info.sequence}')
                    self._emit_local(instance_name, channel_name, info.local_subscribers, message)
                    self._emit_remote(instance_name, channel_name, info.remote_subscribers, message, info.sequence)

    @staticmethod
    def _check_final_subscriber(info: EventSubscriberInfo):
        return info.mode == 'once'

    def _emit_local(
            self, instance_name: str, channel_name: str, subscribers: dict[str, EventLocalSubscriberInfo],
            message: Message):
        source = RoleInstanceID(self.context.profile.name, instance_name)
        final_subscribers = self._convey_event_local(source, channel_name, subscribers, message.args, message.payloads)
        for instance_name in final_subscribers:
            del subscribers[instance_name]

    def _emit_remote(
            self, instance_name: str, channel_name: str,
            subscribers: dict[RoleInstanceID, EventRemoteSubscriberInfo], message: Message, sequence: int):
        final_subscribers = []
        sent_actors: set[str] = set()
        common_tags = {'source_instance_name': instance_name, 'source_channel_name': channel_name, 'sequence': str(sequence)}
        for subscriber, info in subscribers.items():
            if not check_conditions(message.args, info.conditions):
                # we don't need to check sequence here since new subscription cannot be handled when emitting
                continue
            if subscriber.actor_name in sent_actors:
                if self._check_final_subscriber(info):
                    final_subscribers.append(subscriber)
            else:
                tags = {
                    **common_tags,
                    'subscriber_instance_name': subscriber.instance_name,
                }
                try:
                    self.procedure_invoker.invoke_procedure(
                        subscriber.actor_name, EVENT_UNIFIED_MESSAGING_CHANNEL, tags, message.args, message.payloads)
                except Exception as e:
                    self.logger.info(f'error when sending event message to {subscriber.actor_name}: {e}')
                else:
                    sent_actors.add(subscriber.actor_name)
                    if self._check_final_subscriber(info):
                        final_subscribers.append(subscriber)
        for subscriber_instance_name in final_subscribers:
            del subscribers[subscriber_instance_name]

    def _on_receive_event_message(self, sender: str, tags: Tags, args: Args, payloads: Payloads):
        self.thread_manager.add_threaded_task(self._on_receive_event_message_impl, (sender, tags, args, payloads))
        return True

    def _on_receive_event_message_impl(self, sender: str, tags: Tags, args: Args, payloads: Payloads):
        try:
            source_instance_name: str = tags['source_instance_name']
            source_channel_name: str = tags['source_channel_name']
            sequence: int = int(tags['sequence'])
        except (KeyError, TypeError):
            raise AssertionError('incomplete event trigger info')

        source = RoleInstanceID(sender, source_instance_name)
        try:
            with self.subscription_lock.read_lock():
                conveyer = self.subscriptions_by_source_channel[source][source_channel_name]
        except KeyError:
            self.logger.exception(
                f'received unexpected event message from channel {source_instance_name}/{source_channel_name}')
            raise
        else:
            with conveyer.lock:
                final_subscribers = self._convey_event_local(
                    source, source_channel_name, conveyer.subscribers, args, payloads, sequence)
                for subscriber_instance_name in final_subscribers:
                    del conveyer.subscribers[subscriber_instance_name]

    def _convey_event_local(
            self, source: RoleInstanceID, channel_name: str, subscribers: dict[str, EventLocalSubscriberInfo],
            args: Args, payloads: Payloads, sequence: int = -1) -> list[str]:
        """ Returns a list of "final subscribers" - those who should no longer receive event message in this channel """
        final_subscribers = []
        for subscriber_instance_name, info in subscribers.items():
            if info.sequence > sequence >= 0:
                continue
            if not check_conditions(args, info.conditions):
                continue
            # once the threaded task has submitted, we don't care if it finishes successfully or not
            thread_args = (source, channel_name, subscriber_instance_name, info.handler, args, payloads)
            self.thread_manager.add_threaded_task(self._handle_event_message, thread_args)
            self.logger.debug(
                f'event in channel {source}/{channel_name} consumed by subscriber {subscriber_instance_name}, '
                f'event sequence {sequence}, subscriber sequence {info.sequence}')
            if self._check_final_subscriber(info):
                final_subscribers.append(subscriber_instance_name)
        return final_subscribers

    def _handle_event_message(
            self, source: RoleInstanceID, channel_name: str, to_instance_name: str,
            handler: Callable[[RoleInstanceID, Args, Payloads], Any], args: Args, payloads: Payloads):
        # if the role is terminating, OK, there's no need to execute it anymore
        with self._execute_environment_for_role(to_instance_name, None):
            self._handle_call_impl(
                source.actor_name, source.instance_name, to_instance_name, channel_name, handler, args, payloads)

    def _describe_handler(
            self, from_actor_name: str, from_instance_name: str, to_instance_name: str, channel_name: str) -> str:
        return f'event subscriber of {to_instance_name} for {from_actor_name}/{from_instance_name}/{channel_name}'

    # endregion emit

    # region subscription/unsubscription

    def subscribe(self, instance_name: str, target: RoleInstanceID, channel_name: str,
                  handler: Callable[[RoleInstanceID, Args, Payloads], Any],
                  *, conditions: Optional[dict[str, Any]] = None, mode: EventSubscriptionMode = 'forever'):
        with self.role_status_manager.ctrl(instance_name).lock_status_for_execute(Status.DECLARED_COMPATIBLE):
            parsed_conditions = parse_conditions(conditions)
            with self.subscription_lock.write_lock():
                sbs = self.subscriptions_by_source_channel[target]
                if not (convey_table := sbs.get(channel_name)):
                    convey_table = sbs[channel_name] = EventConveyTable()
                # subscription is a two-stepper: request and record
                # the whole process should be atomic, so we need to lock the convey table first
                with convey_table.lock:
                    try:
                        if target.actor_name == self.context.profile.name:
                            self._subscribe_local(
                                instance_name, target.instance_name,
                                channel_name, handler, parsed_conditions=parsed_conditions, mode=mode)
                            sequence = -1
                        else:
                            sequence = self._subscribe_remote(
                                instance_name, target, channel_name, conditions=conditions, mode=mode)
                            assert isinstance(sequence, int)
                    except Exception:   # noqa: using Logger.exception()
                        self.logger.exception(f'failed to subscribe to event {target}/{channel_name}')
                        raise
                    else:
                        if sequence != 0:
                            convey_table.subscribers[instance_name] \
                                = EventLocalSubscriberInfo(mode, parsed_conditions, handler, sequence)
                            self.logger.info(f'subscribed to event {target}/{channel_name}')
                        # sequence == 0 means duplicate subscription
                    finally:
                        if not convey_table.subscribers:
                            del sbs[channel_name]
                        if not sbs:
                            del self.subscriptions_by_source_channel[target]

    def _subscribe_local(self, subscriber_instance_name: str, source_instance_name: str, channel_name: str,
                         handler: Callable[[RoleInstanceID, Args, Payloads], Any], *,
                         parsed_conditions: Iterable[EventConditionChecker], mode: EventSubscriptionMode):
        with self.role_status_manager.ctrl(source_instance_name).lock_status_for_execute(Status.DECLARED_COMPATIBLE):
            try:
                with self.event_lock.read_lock():
                    info = self.events[source_instance_name][channel_name]
            except KeyError:
                raise ChannelNotFoundError(f'{source_instance_name}/{channel_name}') from None
            else:
                with info.lock:
                    info.local_subscribers[subscriber_instance_name] \
                        = EventLocalSubscriberInfo(mode, parsed_conditions, handler)
                    self.logger.info(f'new local event subscriber: '
                                     f'channel {source_instance_name}/{channel_name} from {subscriber_instance_name}')

    def _subscribe_remote(self, instance_name: str, target: RoleInstanceID, channel_name: str,
                          *, conditions: Optional[dict[str, Any]] = None, mode: EventSubscriptionMode = 'forever'):
        tags = {'subscriber_instance_name': instance_name, 'source_instance_name': target.instance_name,
                'channel_name': channel_name, 'subscription_id': str(hash((mode, id(conditions))))}
        args = {'conditions': conditions or {}, 'mode': mode}
        try:
            sequence = self.procedure_invoker.invoke_procedure(
                target.actor_name, EVENT_SUBSCRIPTION_UNIFED_MESSAGING_CHANNEL, tags, args, MyPayloads())
            return sequence
        except InvocationRefusedError as e:
            self.logger.error(f'cannot find event channel {target}/{channel_name}')
            raise ChannelNotFoundError(str(e)) from None
        except InvocationAbortError as e:
            self.logger.error(f'failed to subscribe to event {target}/{channel_name} (subscriber error): {e}')
            raise CallerError(str(e)) from None
        except Exception as e:
            self.logger.error(f'failed to subscribe to event {target}/{channel_name} (source error): {e}')
            raise HandlerError(str(e)) from None    # not technically a handler but OK

    def _on_receive_event_subscription_message(self, sender: str, tags: Tags, args: Args, _: Payloads):
        try:
            subscriber_instance_name: str = tags['subscriber_instance_name']
            source_instance_name: str = tags['source_instance_name']
            channel_name: str = tags['channel_name']
            subscription_id: str = tags['subscription_id']
        except KeyError:
            raise AssertionError('incomplete tags for event subscription')

        conditions = args.get('conditions', {})
        assert isinstance(conditions, Mapping), 'incorrect condition message format'
        try:
            parsed_conditions = parse_conditions(conditions)
        except ValueError as e:     # normally should not happen though
            raise InvocationAbortError(str(e))
        mode = args.get('mode', 'forever')  # type: EventSubscriptionMode

        with self.role_status_manager.ctrl(source_instance_name).lock_status_for_execute(Status.DECLARED_COMPATIBLE):
            try:
                with self.event_lock.read_lock():
                    if source_instance_name not in self.events:
                        raise InvocationRefusedError(f'the role {source_instance_name} is not open')
                    info = self.events[source_instance_name][channel_name]
            except KeyError:
                raise InvocationRefusedError(
                    f'event channel {source_instance_name}/{channel_name} does not exist') from None
            else:
                with info.lock:
                    subscriber = RoleInstanceID(sender, subscriber_instance_name)
                    if (subscriber_info := info.remote_subscribers.get(subscriber)) \
                            and subscriber_info.subscription_id == subscription_id:
                        # duplicate subscription request
                        return 0
                    info.remote_subscribers[subscriber] = \
                        EventRemoteSubscriberInfo(mode, parsed_conditions, subscription_id)
                    info.sequence += 1
                    subscriber_sequence = info.sequence
                self.logger.info(
                    f'new remote event subscriber: channel {source_instance_name}/{channel_name} from {subscriber}')
                return subscriber_sequence

    def unsubscribe(self, instance_name: str, target: RoleInstanceID, channel_name: str):
        with self.role_status_manager.ctrl(instance_name).acquire_execution(), self.subscription_lock.write_lock():
            sbs = self.subscriptions_by_source_channel[target]
            if not (convey_table := sbs.get(channel_name)):
                raise RuntimeError(f'role {instance_name} did not subscribe to {target}/{channel_name}')
            with convey_table.lock:
                try:
                    if target.actor_name == self.context.profile.name:
                        self._unsubscribe_local(instance_name, target.instance_name, channel_name)
                    else:
                        self._unsubscribe_remote(instance_name, target, channel_name)
                except Exception:
                    self.logger.exception(f'failed to unsubscribe from event {target}/{channel_name}')
                    raise
                else:
                    convey_table.subscribers.pop(instance_name, None)
                    self.logger.info(f'unsubscribed from event {target}/{channel_name}')
                    if not convey_table.subscribers:
                        del sbs[channel_name]
                    if not sbs:
                        del self.subscriptions_by_source_channel[target]

    def _unsubscribe_local(self, subscriber_instance_name: str, source_instance_name: str, channel_name: str):
        try:
            with self.event_lock.read_lock():
                info = self.events[source_instance_name][channel_name]
        except KeyError:
            raise ChannelNotFoundError(f'{source_instance_name}/{channel_name}') from None
        else:
            with info.lock:
                info.local_subscribers.pop(subscriber_instance_name, None)

    def _unsubscribe_remote(self, instance_name: str, target: RoleInstanceID, channel_name: str):
        tags = {'subscriber_instance_name': instance_name, 'source_instance_name': target.instance_name,
                'channel_name': channel_name}
        try:
            self.procedure_invoker.invoke_procedure(
                target.actor_name, EVENT_UNSUBSCRIPTION_UNIFED_MESSAGING_CHANNEL, tags, MyArgs(), MyPayloads())
        except InvocationRefusedError as e:
            self.logger.error(f'cannot find event channel {target}/{channel_name}')
            raise ChannelNotFoundError(str(e)) from None
        except InvocationAbortError as e:
            self.logger.error(f'failed to unsubscribe from event {target}/{channel_name} (subscriber error): {e}')
            raise CallerError(str(e)) from None
        except Exception as e:
            self.logger.error(f'failed to unsubscribe from event {target}/{channel_name} (source error): {e}')
            raise HandlerError(str(e)) from None    # not technically a handler but OK

    def _on_receive_event_unsubscription_message(self, sender: str, tags: Tags, _: Args, __: Payloads):
        try:
            subscriber_instance_name: str = tags['subscriber_instance_name']
            source_instance_name: str = tags['source_instance_name']
            channel_name: str = tags['channel_name']
        except KeyError as e:
            raise AssertionError('incomplete tags for event subscription') from e

        with self.role_status_manager.ctrl(source_instance_name).lock_status_for_execute(Status.DECLARED_COMPATIBLE):
            try:
                with self.event_lock.read_lock():
                    info = self.events[source_instance_name][channel_name]
            except KeyError:
                raise InvocationRefusedError(f'event channel {source_instance_name}/{channel_name} does not exist')
            else:
                with info.lock:
                    subscriber = RoleInstanceID(sender, subscriber_instance_name)
                    info.remote_subscribers.pop(subscriber)
                self.logger.info(
                    f'remote unsubscription: channel {source_instance_name}/{channel_name} from {subscriber}')
                return True

    # endregion subscription/unsubscription

    # region automatic subscription management

    @after(target='relationships', method='add_to_relationship')    # synchronized by target method add_to_relationship
    def _advice_after_add_to_relationship(self, activity: InvocationActivity, _result):
        self.thread_manager.add_threaded_task(
            self._advice_after_add_to_relationship_impl, (activity.args[0], activity.args[1]))

    def _advice_after_add_to_relationship_impl(self, relationship_name: str, new_instances: Iterable[RoleInstanceID]):
        with self.subscription_listeners_lock:
            if relationship_name in self.subscription_listeners:
                all_listeners = self.subscription_listeners[relationship_name]
                for subscriber_instance_name, listeners in all_listeners.items():
                    for listener in listeners.values():
                        self._auto_subscribe_impl(subscriber_instance_name, listener, new_instances)

    def _auto_subscribe_impl(self, subscriber_instance_name: str, listener: EventSubscriptionListener,
                             targets: Iterable[RoleInstanceID]):
        handler, properties = listener.handler, listener.properties
        for target in targets:
            if properties.extra_filter(target):
                try:
                    self.subscribe(subscriber_instance_name, target, properties.channel_name,
                                   handler, conditions=properties.conditions, mode=properties.mode)
                except Exception:   # noqa: using Logger.exception()
                    self.logger.exception(f'failed to automatically subscribe to '
                                          f'r/{listener.properties.relationship}/{properties.channel_name}')

    @after(target='relationships', method='remove_from_relationship')   # synchronized by target method remove_from_rel.
    def _advice_after_remove_from_relationship(self, activity: InvocationActivity, _result):
        self.thread_manager.add_threaded_task(
            self._advice_after_remove_from_relationship_impl, (activity.args[0], activity.args[1]))

    def _advice_after_remove_from_relationship_impl(self, relationship_name: str, instances: Iterable[RoleInstanceID]):
        with self.subscription_listeners_lock:
            if relationship_name in self.subscription_listeners:
                all_listeners = self.subscription_listeners[relationship_name]
                for subscriber_instance_name, listeners in all_listeners.items():
                    for listener in listeners.values():
                        self._auto_unsubscribe_impl(subscriber_instance_name, listener, instances)

    def _auto_unsubscribe_impl(self, subscriber_instance_name: str, listener: EventSubscriptionListener,
                               targets: Iterable[RoleInstanceID]):
        extra_filter = listener.properties.extra_filter
        channel_name = listener.properties.channel_name
        for target in targets:
            if extra_filter(target):
                try:
                    self.unsubscribe(subscriber_instance_name, target, channel_name)
                except Exception:   # noqa: using Logger.exception()
                    self.logger.exception(f'failed to automatically unsubscribe from '
                                          f'r/{listener.properties.relationship}/{channel_name}')

    # endregion
