# Message Channels

[//]: # (This document contains one or more tables. A Markdown reader is recommended for better reading experience.)

In RoleML, each role encapsulates a set of message **channels** that serve as interfaces for other roles. Roles send messages to each other via these channels, which forms the _workflow_ of a DML architecture. This document describes the programming interfaces for creating messaging channels and using them in different roles.

Note: the APIs described below, including classes, types, functions and decorators, can be imported in a single line as:

```python
from roleml.essentials import *
```

## Creating Channels

### Services and Tasks

To create a service or task channel, you need to provide a message handler for it. A message sent to this channel represents a call to the handler, and the result will be returned to the caller.

> RoleML is not responsible for guaranteeing the thread safety of a handler.

The difference between a service and a task channel is that _a service call is synchronous_, which means that the caller will be blocked until the handler has finished (either success or failure); while _a task call is asynchronous_, which means that the caller may continue as long as the message has been sent to the caller.

A minimal example is as follows:

```python
class ServiceTaskProvider(Role):

    @Service()
    def echo(self, caller: RoleInstanceID, args: Args, payloads: Payloads):
        return args['comment']
    
    @Task()
    def heavy_job(self, caller: RoleInstanceID, args: Args, payloads: Payloads):
        import time
        time.sleep(5)
        return True
```

By default, a service or task handler must follow the above signature. The `caller` represents the role instance (actor name & instance name) that is calling the service or the task. Meanwhile, `args` and `payloads` are two parts of a message that represent JSON-serializable and other contents, respectively. Both parts are key-value pairs (mapping). When the debug mode is [enabled](../running-distributed-training/1-configuring-node.md#debug), the `args` part of every message will be output via the role's logger.

> The arguments `args` and `payloads` should always be treated as read-only in a message handler.

By default, the name of the handler method will be used as the name of the channel. In the above example, it is `echo`. Note that underscores `_` will be automatically converted to hyphens `-`.

During message handling, you can raise a `CallerError` to indicate that an error has occurred and is due to the caller, such as an invalid content format. Other exceptions raised will be treated as "internal errors" that are not related to the caller (converted to a `HandlerError` at the caller side). In the example above, a `KeyError` will be raised in the service handler if the key `comment` is not available in the message. To indicate that the error is due to the caller, consider raising `CallerError` in a try statement.

### Channel Semantics

You can provide the following additional arguments to the `@Service()` or `@Task()` decorator:

> Note: it is OK to omit the parenthesis if you don't need any configuration. For example, `@Service` is the same as `@Service()`, but it is possible that your IDE will complain about the former.

#### `name`

Specify a custom name for this channel and replace the default value (i.e. the name of the handler method). Again, underscores `_` will be automatically converted to hyphens `-`.

#### `expand`

Instruct RoleML to extract the contents from a message and pass them to the handler directly as keyword arguments. This allows the method handler to be written more like a normal public method. For example, the `echo` handler described above can be rewritten with `expand=True` as:

```python
class ServiceTaskProvider(Role):

    @Service(expand=True)
    def echo(self, caller, comment: str):
        return comment
```

Note that a missing required argument will be considered as an "internal error".

### Events

An event channel is declared as a class attribute in a Role subclass:

```python
class EventSource(Role, Runnable):

    my_event = Event()
```

By default, the name of the event channel is the same as the attribute name. You can specify a custom name as `Event("my-custom-name")`. No matter which one to take, all underscores `_` will be replaced by hyphens `-`.

## Using Channels

### Referencing Role Instances via Relationships

Most edge-oriented DML systems only support centralized architectures, notably Federated Learning. In these architectures, the communication between nodes is simple: clients only interact with the server, while the server maintains the list of clients from which it can choose the lucky ones to interact with.

However, in RoleML, we focus on more fine-grained units: roles. It is common that a role needs to interact with multiple types of roles to fulfill its responsibility. Since these roles can be distributed in different nodes, we can't just make them visible as instance attributes. So how do we know which role(s) to send message(s) to? 

To solve this problem, RoleML introduces a new abstraction called _relationship_. Each relationship is a reference of a list of instantiated roles at runtime. For example, a relationship named `trainer` may contain a list of Trainer instances on different clients, from which a Client Selector can select participants for the next training round.

Relationships are configured at the node level, so that the same relationships can be shared by all roles that are deployed on the same physical node. From another perspective, the relationships managed by each individual node can be considered to contain a partial view of the overall DML topology.

### Calling Services and Tasks

To call a service on another role, use the `Role.call()` API. A typical usage is:

```python
class AnotherRole(Role, Runnable):

    def run(self):
        self.call('service-provider', 'echo', args={'comment': 'helloworld'})
        # you can also write
        self.call('service-provider', 'echo', args=MyArgs(comment='helloworld'))
```

These two call statements are equivalent. It means calling the service on the role instance that belongs to the relationship `service-provider` from the current actor's perspective. If there are multiple eligible role instances, RoleML does not guarantee which one will be called, and you should use `call_group()` instead if you need to send messages to all of them.

> Note that this role implements the `Runnable` interface, which means that its `run()` method will be automatically submitted to a thread as long as a role deployed is ready for messaging. See [this document](./5-role-lifecycle.md) for more detail about role status.

If there is no role instance belonging to the given relationship, RoleML will try to locally find a role with the same name (the name of a role is not necessarily the same as the name of its class). Therefore, if the provider role is deployed on the same actor and is named `service-provider`, you don't need to configure the relationship.

> A role instance named `service_provider` will not be recognized here. We recommend to always use hyphens `-` instead of underscores `_` in both relationship and role instance names.

> Note that if you intend to move the provider role to another actor, you do need to configure the relationship properly.

As always, all underscores `_` in the channel name will be automatically converted to hyphens `-`.

You can also call a given role instance:

```python
class AnotherRole(Role, Runnable):

    def run(self):
        self.call(RoleInstanceID('alice', 'provider'),
                  # or RoleInstanceID.of('alice/provider')
                  'echo', args={'comment': 'helloworld'})
```

A task can be called with the `call_task()` API, similar to the API for service call. `call_task()` will return a Future-like object representing the current call, with a `result()` method that can be used to wait for the result.

```python
class AnotherRole2(Role, Runnable):

    def run(self):
        future = self.call_task('task-provider', 'heavy-job')
        print(future.result())  # block until task has been finished
```

### Emitting Events

When a role is deployed, an instance attribute with the same name as the corresponding class attribute will be assigned to the role, with which you can emit event messages:

```python
class EventSource(Role, Runnable):

    my_event = Event()

    def run(self):
        self.my_event.emit(args=..., payloads=...)
```

Technically, you can emit event messages when a role instance is in the `READY` status. This means that you can do so in a service or task handler, an event handler, or any methods called by them. You can also do so in the `run()` method if your role implements the [`Runnable`](./2-role-overview.md#runnable-role) interface. See [this document](./5-role-lifecycle.md) for more detail about role status.

### Subscribing to an Event Channel

#### Automatic Subscription

You can make a role automatically subscribe to an event channel of role instances that belong to a given relationship by annotating an event handler. An example is as follows:

```python
class EventSubscriber(Role):

    @EventHandler('event-source', 'my-event')
    def handler(self, source: RoleInstanceID, args: Args, payloads: Payloads):
        ...
```

The following code snippet states that an instance of the `EventSubscriber` role should subscribe to the `my-event` channel of role instances that belong to the relationship `event-source`. Subscription and unsubscription are automatically conducted when role instances are added to and removed from the relationship, respectively.

You can specify the [mode](#subscription-modes) and [conditions](#subscription-conditions) when making an annotation.

> RoleML is not responsible for guaranteeing the thread safety of an event handler.

Note that if the given relationship refers to an empty set when starting the role instance, RoleML will search for a local role instance with the same name as the relationship and try to subscribe to the given channel of it. Once success, the subscription will not be automatically removed when other role instances are added to the relationship.

#### Manual Subscription

You can use the `subscribe()` API if you intend to subscribe to an event channel of a specific role instance. Similarly, the `unsubscribe()` API is available for manually removing an existing subscription.

#### Subscription Modes

When making a subscription, you can specify one of the two subscription modes:

* `once`: only receive at most one event message, after which the subscription will be automatically removed.
* `forever` (default): always receive event messages if they match the given conditions.

#### Subscription Conditions

When making a subscription, You can specify conditions to filter out unwanted events. The conditions should be organized as a dictionary, where each key corresponds to a key in the `args` part of an event message and its value is the criterion, which should be a literal value. You can additionally provide a key with an [operator](#operator-list) (in the format `msg_key__op`) for more precise control.

For example, assume a role emits the following event messages in a given channel:

```python
msg1 = Message(MyArgs(a=1, b=2, c="4"), MyPayloads(d=8, e="16"))
msg2 = Message(MyArgs(a=2, b=4, c="8"), MyPayloads(d=16, e="32"))
msg3 = Message(MyArgs(a=4, b=8, c="16"), MyPayloads(d=32, e="64"))
```

If another role subscribes to this channel by providing the conditions `{'a': 1}`, it will only receive `msg1` whose value of `a` equals to `1`.

More examples are as follows:

| Conditions | Event Messages Received | Explanation |
|---|---|---|
| `{'a__gt': 1}` | `msg2`, `msg3` | The value of `a` is greater than `1`. |
| `{'a__gt': 1, 'c': "16"}` | `msg3` | The value of `a` is greater than `1`, AND the value of `c` is exactly `"16"`. |
| `{'d': 32}` | None | The payloads part will not be used in condition checking. Since no event message contains the key `d` in `args`, the subscriber will not receive any of them. |

The full list of operators can be found [below](#operator-list).

##### Operator List

| Operator | Meaning |
|---|---|
| `eq`, `==` | The corresponding value in a message must exactly be the provided value. |
| `gt`, `&gt;` | The corresponding value in a message must be greater than the provided value. |
| `ge`, `&gt;=` | The corresponding value in a message must be greater than or equal to the provided value. |
| `lt`, `&lt;` | The corresponding value in a message must be less than the provided value. |
| `le`, `&lt;=` | The corresponding value in a message must be less than or equal to the provided value. |
| `contains` | The corresponding value in a message should be a list containing the provided value. |

A missing operator is equivalent to `eq`.
