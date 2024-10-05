# Role Overview

## The Role Model

In RoleML, roles are functional components that interact with each other within a DML architecture. Each role encapsulates a set of message **channels** that serve as interfaces for other roles. There are three types of channels: _services_ and _tasks_ stand for synchronous and asynchronous function calls respectively, which are used in directional communication. _Events_ follow the publish-subscribe model and are used for non-directional communication. All channels defined in a role should focus on a single responsibility such as training or aggregation.

Meanwhile, as a best practice, a DML architecture should decouple its workflow (i.e. the what-to-do part) from the specific implementation of the workloads (i.e. the how-to-do part, such as what model to train, and with what dataset). RoleML achieves such decoupling via an abstraction for different kinds of workloads, namely **element**. A workload element specifies the base class or interface of _workload objects_ that will be created or loaded for the role. In other words, it expresses _the need for a certain type of object(s) in order to make a role work_. 

## Role Programming Overview

Each type of role is defined as a subclass of the `Role` base class, which is also called a _role class_. A _role_ (or a _role instance_) is instantiated from a role class and also the basic deployment unit of RoleML.

### Message Channels

For a single role, a service or task channel is represented by a handler (defined in the role class) that handles messages sent to the channel and return the results back to their senders (aka "callers"). An event channel (declared in the role class) can be subscribed by other roles so that messages emitted from this channel can be received by these subscribers. Each subscription also requires a message handler on the subscriber side to handle the event messages.

The interaction between different roles via these message channels forms the _workflow_ of a DML architecture. See [this document](./3-channels.md) for more detail about defining message channels for a role and performing role interactions using these channels.

### Workloads

A workload element is declared by a role class. When declaring a workload element, you don't need to care about where a workload object may come from (for example, does it come from a factory or as an existing singleton?). In fact, you can provide different implementations for different instances of the same role class. When an implementation is provided, the corresponding role instance will receive a proxy object, which is called an _element instance_, that contains the detail of the implementation and can be called to obtain a concrete workload object.

See [this document](4-workload.md) for more detail about defining and using workload elements.

### Logging

Each role holds an instance attribute named `logger`, which is a standard Python logger. See [the official document of the standard `logging` module](https://docs.python.org/3/library/logging.html) to learn about how to use a logger.

See [node configuration](../running-distributed-training/1-configuring-node.md) for more information about configuring the output of log messages.

### Application Context

See [this document](6-application-context.md) for more detail about application context and access APIs.

### `Runnable` Role

A role class can optionally implement the `Runnable` interface (imported via `roleml.essentials.Runnable`) by defining the `run()` method, which is also called the main routine. As such, when an instance of it is started in an actor, the main routine will be submitted to a separate thread as a bound method.

> Warning: to make sure the actor can exit gracefully, do not let the main routine run forever, or at least make the main routine interruptable and implement the `stop()` method in this interface to interrupt it. The `stop()` method will be automatically called when the role is to be removed.
