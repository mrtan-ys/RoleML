# Native Role

## Introduction

The default implementation of a RoleML actor exposes many management APIs to a special role, which is named the _native role_. Every actor starts with a native role named `actor`. This allows operations like role assignment and relationship adjustment to be done dynamically at runtime, enabling many advanced features for distributed training including dynamic topology.

Note that in order to call a service or task on a native role, the caller must be recognized as a _manager_ of the target actor by being added to the `manager` relationship of the target actor.

## Channels

### service `update-contacts`

Update contact information on the target actor.

An actor can only send messages to another actor if the contact information of that actor is known to the current actor.

#### Args

##### `contacts` (dict[str, str])

Contact information to update. It should map the name of each actor to its network address.

#### Returns

None. An event will be triggered in channel `contact-updated` for every actor with contact information updated.

***

### event `contact-updated`

Indicates the contact information of an actor has been updated. That is, its network address known to the current actor has been added or changed.

#### Args

##### `name` (str)

The name of the actor with contact information updated.

***

### service `update-relationship`

Update a relationship on the target actor.

#### Args

##### `relationship_name` (str)

The name of the relationship to update.

##### `op` (str)

The desired operation, which must be `add` for adding roles and `remove` for removing roles.

#### Payloads

##### `instances` (list[RoleInstanceID])

The role instances to be added to or removed from the given relationship.

***

### event `relationship-updated`

Indicate that a relationship of the current actor has been updated.

#### Args

##### `name` (str)

The name of the relationship.

##### `op` (str)

The operation performed, which is `add` for adding roles and `remove` for removing roles.

##### `instances` (list[RoleInstanceID])

The role instances added to or removed from the relationship.

***

### service `add-relationship-link`

Add a [relationship link](../system-model/6-application-context.md#relationship-links) to the target actor.

#### Args

##### `from_relationship_name` (str)

The name of the relationship link, i.e. an alias of an existing relationship (specified by `to_relationship_name`). There should be no role instance that belongs to the relationship named `from_relationship_name`.

##### `to_relationship_name` (str)

The name of the original relationship.

#### Returns

None.

***

### task `assign-role`

Assign a new role to the target actor. The role is created in-place with given configuration. Does not return until the corresponding role has been started (i.e. in the [READY](../system-model/5-role-lifecycle.md#role-status) status).

#### Args

##### `name` (str)

The name of the new role.

##### `spec` (RoleSpec)

The configuration of the new role. See [this document](2-configuring-role.md) for more detail.

#### Returns

None. An event will be triggered in channel `role-assigned` when a role is assigned and started successfully.

***

### event `role-assigned`

Indicate that a new role has been added to the current actor.

#### Args

##### `name` (str)

The name of the new role.

##### `cls` (str)

The name of the class of the new role.

***

### task `terminate-role`

Remove an existing role from the target actor. Does not return until the removal is completed.

#### Args

##### `name` (str)

The name of the role to remove.

***

### event `role-removed`

Indicate that a role has been removed from the current actor.

#### Args

##### `name` (str)

The name of the role that has been removed.

***

### service `get-role-status`

Get the [current status](../system-model/5-role-lifecycle.md#role-status) of an existing role on the target actor.

#### Args

##### `name` (str)

The name of the role.

#### Returns

A `Status` enum object indicating the current status of the corresponding role. For example, `Status.READY` indicates that the role is in the `READY` status.
