# Adding or Removing Roles Dynamically

## Adding a New Role

### Using Actor API

If you have access to the actor object, you can use its API to deploy a new role while the actor is running. Basically speaking, the whole process contains the following steps:

1. Prepare the role class and create a new role instance.
2. Add the role instance to the actor using `Actor.add_role()`.
3. Implement workload elements using `Actor.implement_element()`. Each element requires a separate API call.
4. Start the role instance using `Actor.start_role()`. This will put the role instance in the READY status, and it will be ready to accept new service or task calls, handle event subscriptions and emit event messages.

> See [this document](../system-model/5-role-lifecycle.md) for more detail about role status.

### Using Native Role (Recommended)

The bundled, default implementation of an actor introduces a _native role_, which encapsulates some management APIs for the actor as well as the application context, and exposes them as service and task channels. Therefore, we can use another role to call the native role on the target actor to assign a new role instance to it. More detail can be found [here](./6-using-native-role.md#task-assign-role).

## Removing an Existing Role

### Using Actor API

If you have access to the actor object, you can use its API `Actor.stop_role()` to remove a role instance from the actor. Note that this is a blocking method, and you may need to wait for the role to finish ongoing jobs (such as service or task calls) before it can be finally removed.

Technically, a role instance needs to go through a series of status transfer until reaching the TERMINATED status, which means it can be safely removed. However, despite that there are APIs for controlling the status, it is generally not recommended to use them directly unless you are developing new functionalities for actors.

### Using Native Role (Recommended)

The _native role_ mentioned above also includes a task channel to remove an existing role instance. More detail can be found [here](./6-using-native-role.md#task-terminate-role).
