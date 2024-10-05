# Application Context

When running a DML application, each node maintains its own version of the application context, which includes the items described below.

The context is encapsulated in a `roleml.core.context.Context` object and is available via `Role.ctx`.

## Contacts

A dictionary mapping each actor name to its address, usually in the form `<ip>:<port>`. This dictionary is maintained by each actor individually, so it only contains the addresses of other actors that it "knows".

_Available as the `contacts` attribute._

## Relationships

The [relationships](./3-channels.md#referencing-role-instances-via-relationships) configured for the current actor.

_Available as the `relationships` attribute, containing several APIs for relationship CRUDs._

### Relationship Links

The relationship linking mechanism is used to create _aliases_ for existing relationships. For example, given a relationship named `trainer`, a link `client -> trainer` can be viewed as using `client` as an alias of `trainer`, and the relationship `client` will always contain the same list of role instances as the relationship `trainer`.

It is useful in solving compatibility issues, when different relationship names are defined in different roles, which is sometimes helpful in improving readability.

Relationship links can be created via `Context.relationships.link_relationship(name, alias)`. Once a link is created, `name` and `alias` can be used interchangeably, and therefore the link cannot be removed.

## Random Seed

The random seed (integer type) configured when starting the current actor. For maximum reproducibility, every random number generator used by the current actor should be initialized with the same seed.

_Available as the `seed` attribute._

## Start Time

The time when the actor is started. More accurately, it is the time when the context object is built.

_A floating-point number timestamp is available as the `start_time` attribute._

_A formatted time string is available as the `start_time_formatted` attribute. The time format is `'%Y-%m-%d-%H-%M-%S'`._

## Working Directory

The working directory of the current actor. It should not be changed once the actor has started.

_Available as the `workdir` attribute._

## Source Directory

The directory of the source code. It will be added to `sys.paths` so that you can organize the source code into packages and import them accordingly.

_Available as the `src` attribute._

## Handwave Actors

List of actors to handwave with when the current actor terminates. A handwave is used to announce termination of the current actor. The handwave targets are specified by their names and must have been added to the contacts.

Note that a handwave only notifies another actor to remove contact information gracefully. Application-specific logic for actor termination (such as client leaving) should be implemented by custom roles.

_Available as the `handwaves` attribute._
