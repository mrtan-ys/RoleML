# Writing the Configuration of a Node

## Introduction

The recommended way to start an actor (which represents a node in a distributed environment) is by using a starting script. This allows the configurations to be provided via a separate file, which is safer and easier to manage. This document introduces the configuration schema accepted by RoleML's bundled starting scripts. For more detail about the scripts, see [this document](4-running-actor.md#running-via-script).

> RoleML uses the YAML format by default. It has been [extended](../z-misc/yaml-extended.md) to support file inclusion, which allows splitting a configuration into multiple files.

## Configuration Schema

### Basic Configurations

#### `name`

Name of the actor. Will be used to identify the current node in a distributed environment.

_Required field._

#### `address`

Network address of the actor. It should contain the host identifier (host name or IP address) as well as a port number. On the one hand, it represents the address to which other actors should send messages when interacting with the roles on it. This also means the messaging component should run on the given port number. On the other hand, messages sent from the current actor should take the corresponding host IP address as the source IP address in order to pass the authentication on the receiver side.

Due to compatibility issues, please _always consider providing an IP address instead of a host name_.

_Required field. If intended to disable message receiving, set it to 127.0.0.1._

#### `roles`

The roles to add to the actor during startup. Each role is identified by a name. Therefore, the configuration provided should be a dictionary that maps the name of each role to its concrete configuration. See [this document](./2-configuring-role.md) for more detail about role configuration.

#### `relationships`

A dictionary (KV pairs) of initial relationships. Each key is the name of a relationship and maps to a list of role instance names (provided as `<actor-name>/<instance-name>`).

#### `relationship_links`

A dictionary (KV pairs) of initial [relationship links](../system-model/6-application-context.md#relationship-links). A relationship link creates an alias for an existing relationship. Once configured, a relationship link cannot be removed.

#### `contacts`

Network addresses of other actors. Should be provided as a dictionary (KV pairs) that maps the name of each actor to its address.

#### `handshakes`

List of actors to handshake with when the current actor starts. A handshake is used to announce existence of the current actor. The handshake targets are specified by their names and must have been added to the contacts.

If the handshake with any actor specified in the list fails, the startup will be considered failed and handwave with actors specified in `handwaves` will be triggered before the current actor exits.

#### `handwaves`

List of actors to handwave with when the current actor terminates. A handwave is used to announce termination of the current actor. The handwave targets are specified by their names and must have been added to the contacts.

Note that a handwave only notifies another actor to remove contact information gracefully. Application-specific logic for actor termination (such as client leaving) should be implemented by custom roles.

### Messaging Components

Each messaging component can be configured in either of the following formats:

* a string representing the fully-qualified name of the component class. If the class is imported successfully, it will be called with no arguments to construct a new instance, which will be used as the corresponding messaging component.
* a dictionary with the following keys: `type` for the fully-qualified name of the component class; `options` for the keyword arguments that will be passed to the `__init__()` method of the new component instance.

#### `procedure_invoker`

The component to dispatch messages to other actors and receive their responses (i.e. procedure invocation).

A component must be explicitly specified in order to enable message dispatching. Otherwise, this feature will be disabled, and the roles on the actor will not be able to call services or tasks, or send event messages if the target role is on another actor (an error will be raised when trying to do so). However, it does not affect the capability to receive messages from other actors, which is provided by the procedure provider.

RoleML includes the following implementations of procedure invoker:

* `roleml.extensions.messaging.invokers.requests.RequestsProcedureInvoker`: a procedure invoker based on the `requests` package.
* `roleml.core.messaging.null.ProcedureInvokerDisabled`: a special implementation for disabling the messaging dispatching feature.

#### `procedure_provider`

The component to receive messages from other actors and send responses to them.

A component must be explicitly specified in order to enable message receiving. Otherwise, this feature will be disabled, and the roles on the actor will not be able to handle service or task calls, or receive event messages if the source (caller) role is on another actor (an error will be raised when trying to do so). However, it does not affect the capability to send messages from other actors, which is provided by the procedure invoker.

RoleML includes the following implementations of procedure provider:

* `roleml.extensions.messaging.providers.flask.FlaskProcedureProvider`: a procedure provider based on the `flask` package.
* `roleml.core.messaging.null.ProcedureProviderDisabled`: a special implementation for disabling the messaging receiving feature.

#### `collective_implementor`

The component to perform collective communications, i.e. it provides implementations for the group messaging APIs `Role.call_group()` and `Role.call_task_group()`.

RoleML includes the following implementations of collective implementor:

* `roleml.actor.group.impl.sequential.SequentialCollectiveImplementor`: uses a single thread to send a batch of messages sequentially.
* `roleml.actor.group.impl.threaded.ThreadedCollectiveImplementor`: uses multithreading to send a batch of messages concurrently.
* `roleml.actor.group.impl.null.CollectiveImplementorDisabled`: a special implementation for disabling the collective communication feature.

#### Compatibility

| Invoker \ provider | `FlaskProcedureProvider` |
|--|--|
| `RequestsProcedureInvoker` | Yes |

### Misc

#### `workdir`

The working directory.

Defaults to the directory where the script was run.

#### `src`

The source code directory. It will be added to `sys.paths` to allow package and module finding.

If not specified, the working directory will be treated as the source code directory.

#### `log_file_path`

The directory to save the log file of the current actor run. The file will be named `<actor-name>/<start-time>.log` under the given directory, so that the same directory can be shared by a batch of actors, each logging to a separate file.

You can add templates to the path name, which will be automatically translated to actual values at runtime. The format of a template is `$<name>`. Supported templates include:

* `random`: a random number between 1 and 2147483647.
* `timestamp`: an integer timestamp representing the startup time of RoleML.
* `time`: a formatted string representing the startup time of RoleML. For example, `2024-06-21-11-01-29`.
* `workdir`: the working directory of the current RoleML run. Can be configured via [`workdir`](#workdir).
* `src`: the source code directory of the current RoleML run. Can be configured via [`src`](#src).
* `seed`: the random seed. Can be configured via [`seed`](#seed).

For example, the path template `logs/$time` will be ultimately translated to something like `logs/2024-06-21-11-01-29`.

#### `log_file_level`

The minimum level of file logging. Only log messages whose level is higher than the specified level will be saved to the target file. See the [official document for `logging`](https://docs.python.org/3/library/logging.html#logging-levels) for more detail about log levels.

When specified, it must be a string indicating the desired log level (case-insensitive). The following levels are supported (from low to high): `DEBUG`, `INFO` (default), `WARNING`, `ERROR`, `CRITICAL`.

Specifying `DISABLED` will disable logging to file.

> Dev note: RoleML also supports another log level `INTERNAL`, which is lower than `DEBUG`. It is intended for developers who are developing new functionalities for RoleML (e.g. by customizing the actor class). General users of RoleML should avoid using this level.

#### `log_console_type`

The type of console (stdout) logging. There are two types:

* `single` (default): used when the standard output is exclusively used by a single actor.
* `shared`: used when the standard output is shared by multiple actors, each running in a subprocess. In this case, every log message will contain the name of the source process to help distinguish between different actors. When using RoleML's [bundled scripts](4-running-actor.md#basic-scripts) to start multiple actors, the process name of every actor will be automatically updated to include the name of the actor, so that you will know which actor logs the message.

#### `log_console_level`

The minimum level of console logging. Only log messages whose level is higher than the specified level will be output to the standard output, which is usually the console. See the [official document for `logging`](https://docs.python.org/3/library/logging.html#logging-levels) for more detail about log levels.

When specified, it must be a string indicating the desired log level (case-insensitive). The following levels are supported (from low to high): `DEBUG`, `INFO` (default), `WARNING`, `ERROR`, `CRITICAL`.

Specifying `DISABLED` will disable logging to standard output.

> Dev note: RoleML also supports another log level `INTERNAL`, which is lower than `DEBUG`. It is intended for developers who are developing new functionalities for RoleML (e.g. by customizing the actor class). General users of RoleML should avoid using this level.

#### `debug`

Indicates whether debug mode is enabled. Currently, it only affects logging - with debug mode on, log messages at `DEBUG` or higher level will always be visible, no matter what `log_console_level` or `log_file_level` is.

Default to False, which means the debug mode is disabled.

> Dev note: log messages at the `INTERNAL` level will only be visible when manually setting `log_console_level` or `log_file_level`. It does not require debug mode to be enabled.

#### `seed`

Random seed. This seed will be saved to the application context. To ensure reproducibility, every random number generator should be initialized with the same seed (e.g. `np.random.seed()`). The standard `random` package is automatically initialized with this seed.

Default to -1, which means the seed will be chosen randomly.

This property will also be saved to the [application context](../system-model/6-application-context.md#random-seed).
