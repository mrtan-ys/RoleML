# Role Lifecycle

[//]: # (This document contains one or more tables. A Markdown reader is recommended for better reading experience.)

## Introduction

The lifecycle of a role contains several statuses as defined in [this table](#role-status).

In RoleML, you can add new roles to an existing actor at any time. You can also decide to remove a role when you don't need it anymore. When your DML application contains such dynamics, it is important to know what will happen when a role is transferred to a new status, which is detailed in [this table](#status-transfer-outcomes).

To add a role, you can provide its configuration when starting the actor, or use the [native role](../running-distributed-training/6-using-native-role.md) to dynamically assign it remotely.

To remove a role, the recommended way is to use the [native role](../running-distributed-training/6-using-native-role.md).

## Role Status

[//]: # (DO NOT FORMAT THIS TABLE SINCE IT WILL MAKE IT UGLIER; USE A MARKDOWN READER)

| Status | Meaning | Transferred to When |
|---|---|---|
| DECLARING | The initial state. | The role is added to an actor. |
| DECLARED | The role's behavior (channels and elements) have been determined. | All declarations in the corresponding role class have been processed. |
| STARTING | The role will be ready for use after some starting jobs. | Calling the actor API to start the role instance. For most use cases, this is automatic. |
| READY | The role is started (active). | The starting jobs are finished. |
| TERMINATING | The role is about to terminate. | Calling the actor API to do so. When trying to terminate a role via the native role, the latter is responsible for calling the actor API. |
| FINALIZING | The role will terminate after doing some finalizing jobs. | All jobs that require to be started in the READY status have finished. |
| TERMINATED | The role is terminated and will be completely removed from the actor. | The finalizing jobs are finished. |

Status transfer is managed by the underlying actor, so normally you don't need to care about it. However, it is important to know what the current status means for message channels and workload elements. [The following table](#status-transfer-outcomes) describes what will happen in each status of a role.

## Status Transfer Outcomes

[//]: # (DO NOT FORMAT THIS TABLE SINCE IT WILL MAKE IT UGLIER; USE A MARKDOWN READER)

| Status | Services/Tasks | Events | Elements | Others |
|---|---|---|---|---|
| DECLARING | Channels defined in the role class are registered. | Channels declared in the role class are registered.<br>Auto subscriptions defined in the role class are pre-registered.<br>If the name of the role instance is not used as a valid relationship name (i.e. does not match any role instance), temporarily create a relationship with this name and the current role being its only role instance and process local automatic subscriptions. |  |  |
| DECLARED |  | The role instance can now make subscriptions to event channels of other role instances.<br>However, auto subscriptions will not be executed until transferred to STARTING. |  |  |
| STARTING |  | Auto subscriptions registered are executed for the first time. | For every element missing an implementation, attempt to make an implementation out of the default configurations specified in the declaration. |  |
| READY | The role instance can now accept calls from other role instances. | The role instance can now emit event messages.<br>Event handlers can now be called when receiving event messages. If a message has arrived before the role is in this status, it will be consumed by the corresponding handler now. |  | If the role implements `Runnable`, its main routine (defined as the `run()` method) will be submitted to a thread as a bound method. |
| TERMINATING | The role instance can no longer accept new calls.<br>Transfer to the status FINALIZING will not proceed until all ongoing service and task calls have finished the handler execution. | The role instance can no longer emit new event messages.<br>Event handlers can no longer be called.<br>New subscriptions can no longer be made.<br>Transfer to the status FINALIZING will not proceed until all ongoing event message delivery and event handler calls have finished. |  |  |
| FINALIZING | Channels registered are removed.<br>Unsent call results will continue to be sent to their callers. | Automatic subscriptions are removed.<br>Registered subscriptions to other event channels are removed, and the corresponding actors of the event sources are notified with the role termination.<br>Channels registered are removed, and the corresponding actors of the subscribers are notified with the role termination. | For every element declared in the role class and implemented in the role instance:<br>1. Call its serializer if available, and then<br>2. Call its destructor if available. | The main routine will be asked to stop by invoking the `stop()` method. Transfer to the status TERMINATED will not proceed until the main routine exits. |

