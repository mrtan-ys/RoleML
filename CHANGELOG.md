# RoleML Changelog

## v0.3.0 (first published version)

**This version is a major refactor. All existing users of v0.2.x should migrate to this version since older versions will no longer be supported.**

### Programming Model

* The role programming APIs are now more intuitive. The `declare()` method is removed. Services, tasks, and event handlers are now declared using annotation decorators. Events and workload elements are now declared using class attributes. Users can leverage the `__init__` method to define initialization parameters and provide arguments in a configuration file.
* The `subscribe_group()` and `unsubscribe_group()` APIs are permanently removed.
* The relationship linking mechanism is introduced to create aliases for a given relationship.
* The relationship manager APIs are now simplified.
* The workload element dependency mechanism is removed.

### Application Interface

* Running via Conductor
    * Configuration format for messaging components is changed in accordance to the message handling system refactor.
    * Configuration format for contacts is changed.
    * Automatic schema validation is introduced for Conductor configuration files (`appConfig`).
    * The Conductor now takes a single node as the deployment unit. Meanwhile, a new configuration property `deployment_order` is introduced to allow specifying which nodes should accept deployment first.
    * The format of templates in an `appConfig` file is modified.
    * The actor running the Conductor role will now stop gracefully when reading an EOF from the standard input.
* Shortcut modules are added to allow one-line import of most common APIs.
* A new feature, element preset, is introduced to allow pre-configuration of the elements to load for specific roles.

### Internal Architecture

* The message handling system is refactored:
    * Messaging component chains are removed. Each actor is now only allowed one procedure invoker and one procedure provider.
    * The messaging components now only focus on sending and/or receiving messages via the network.
    * As a result, the three addresses of a node (service address, task address and event address) are combined into one.
    * A new mechanism for performing handshake and handwaving between nodes is introduced.
    * An optimization is introduced to prevent duplicate serialization of the same message.
* A gRPC implementation of the messaging component is now available.
* Workload elements and the role status of a role are no longer managed by the role itself.
* The responsibilities of an actor are now distributed to multiple _managers_. Meanwhile, the new actor base class (`BaseActor`) can be inherited more easily to allow customized managers.
* Along with the actor refactor, the actor builder base class (`BaseActorBuilder`) is now more extensible.
* Along with the actor refactor, a plugin mechanism is added to allow detecting customized attributes in role definition that works with a customized manager.
* A new role status `STARTING` is introduced to represent the transition from `DECLARED` to `READY`. Meanwhile, `UNDECLARED` is renamed `DECLARING`.

### Standard Library

* The abstract interfaces for models and datasets are redefined.
* The template classes for PyTorch models are updated for better modularity.
* The helper classes (such as dataset views and index samplers) are updated. The alias of built-in index samplers are also changed.
* The Trainer role in the library is updated. Now there are two variants: `EpochTrainer` and `GradientTrainer`.

### Other Changes

* When enabling the built-in native role, any changes to a relationship will now trigger an event from the native role. In the past, this was not true when directly operating on the relationship manager.
* When sending a message to a remove node, both `args` and `payloads` are now serialized using `pickle`.
* The logging system is refactored. More loggers are added to help debugging. Meanwhile, a new log level `INTERNAL = 5` is introduced for developers who are customizing RoleML.
* Support for simulating DML in one process is added.
* The runtime CLI, used by the Conductor role, now ignores command lines starting with `#`.
* More helper APIs are added to `roleml.shared`.
* Bugfixes.
