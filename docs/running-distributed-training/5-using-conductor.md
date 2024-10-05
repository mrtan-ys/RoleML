# Using the Conductor Role to Conduct an Experiment

RoleML comes with a helper role class _Conductor_ for conducting experiments on a DML architecture. This allows the initial workflow of a DML architecture to be encapsulated in a message channel and therefore a DML training session can be initiated remotely from another role controlled by the experiment organizer.

A Conductor creates a runtime CLI so that you can enter commands in the console to control it. The `Conductor` base class in the `roleml.library.roles.conductor.base` module defines a command `configure`. It reads a configuration file and deploy the configuration to other pre-started actors to get them prepared for a DML run.

To experiment with your own architecture, a typical process would be:

0. Prepare the roles (Trainer, Aggregator, Coordinator, etc.) for your architecture.
1. Create a Conductor subclass and [add custom commands](#customizing-conductor).
2. Prepare the [configuration](#conductor-configuration) for an experiment.
3. Start the actors required by the experiment. These actors' network addresses should match the specification in the configuration.
4. Open a new console and start an actor with the custom Conductor deployed.
5. Type the command `configure path/to/your/configuration/file` to load the configuration and deploy it to the already-started actors.
6. Type the custom command(s) to control a DML run.

## Customizing Conductor

You can customize a Conductor for experimenting with your architecture by subclassing the `Conductor` base class. 

A new command can be added via `Conductor.cli.add_command()`. For example:

```python
class MyConductor(Conductor):

    def __init__(self):
        super().__init__()
        self.cli.add_command('start', self.start, expand_arguments=True)
    
    def start(self, num_rounds: int = 100):
        self.call_task('coordinator', 'run', args={'num_rounds': num_rounds}).result()
```

This code snippet adds a new command `start` to the runtime CLI created by a `MyConductor` instance, with the `start()` method being the handler. The `expand_arguments` option instructs the CLI to extract available arguments for the command from the handler's signature. Therefore, when we start an actor with a `MyConductor` role deployed, we can type the following command in the console:

```shell
run --num_rounds 50
```

which will invoke the `start()` method with `num_rounds=50`. The command format is the same as the one accepted by a `argparse` parser. We can also type:

```shell
run
```

which will invoke the `start()` method with the default value `100` for `num_rounds`.

## Conductor Configuration

A Conductor reads a configuration file and deploys its content to the pre-started actors before an experiment can be run.

When writing a configuration, you are basically writing a **configuration template**. Such a template allows the use of regular expressions and [value templates](#value-templates) in certain places to simplify the configuration of multiple actors.

When reading a configuration template, a Conductor will generate a **reproducible configuration** for the current run. The template will be expanded to include the concrete configuration of every single actor. Feeding the Conductor with the same reproducible configuration file should always yield the same (or similar) experiment results ideally.

### Configuration Schema

#### `profiles`

A list of actors to be directly managed by the Conductor. Such actors are also called **batch actors**. They accept role assignment, contact and relationship configurations directly from the Conductor.

When provided, it should be a list of mapping where each item contains the actor name and its corresponding network address:

```yaml
profiles:
  - name: a1
    address: 192.168.2.1:5001
  - name: a2
    address: 192.168.2.1:5002
  - ...
```

Batch actors should be started before configuration deployment, usually by a [batch staring script](./4-running-actor.md#basic-scripts).

#### `profiles_separate`

A list of actors to be partially managed by the Conductor. Such actors are also called **separate actors**. They only accept contact and relationship configurations directly from the Conductor, while the roles are deployed by themselves.

When provided, it should be a list with the same format as [batch actors](#profiles).

Separate actors should be started before configuration deployment, usually with necessary roles [deployed at startup](./1-configuring-node.md#roles).

#### `profiles_individual`

A list of actors that will not be managed by the Conductor. Such actors are also called **individual actors**. They accept no configuration from the Conductor; only the contact information will be registered to the actor running the Conductor so that the Conductor can interact with roles on these individual actors.

When provided, it should be a list with the same format as [batch actors](#profiles).

Individual actors should be started with necessary roles deployed and contact information added before the Conductor needs to interact with them.

#### `roles`

Role deployment to be done from the Conductor. Should be provided as a mapping that maps each actor name to its role configuration. The role configuration for an actor should be a mapping that maps each role (identified by a string name) to the specific configuration. See [this document](2-configuring-role.md) for more detail about configuring a role.

In a configuration template, the actor name can be a regex that matches one or more batch actors.

#### `connections`

Contact information to be configured via the Conductor. Should be provided as a mapping that maps each actor name to the contact information that will be added to that actor. Such contact information should be a list of actor names, while the addresses of these actors should have been specified in `profiles`, `profiles_separate` or `profiles_individual`.

Be aware that in order to achieve communication between two actors, each of them must know the address of the other. For example, if roles on actor A need to send messages to roles on actor B, then **actor A must be configured with the address of actor B, and vice versa**.

This property does not allow using regex to match multiple actors at the same time. The property [`connection_rules`](#connection_rules) can be used for this purpose.

#### `relationships`

Relationships to be configured via the Conductor. Should be provided as mapping that maps each actor name to the relationships that will be added to that actor. Each relationship should be represented by a KV pair whose key is the relationship name and value is a list of role instance identifiers (role name plus the corresponding actor), such as `a1/trainer` (the role `trainer` on actor `a1`). When the role name is missing, the relationship name is used. For example, `a1` under the relationship `trainer` will be treated as `a1/trainer`.

This property does not allow using regex to match multiple actors at the same time. The property [`relationship_rules`](#relationship_rules) can be used for this purpose.

#### `relationship_links`

Relationship links to be configured via the Conductor. Should be provided as mapping that maps each actor name to the relationships links that will be added to that actor. A relationship link should be a KV pair whose value is the original relationship name and key is the alias.

In a configuration template, the actor name can be a regex that matches one or more batch, separate, or individual actors.

#### `connection_rules`

This property is used to configure contact information of actors in batches. It should be provided as a list where each item is a string like `<from> <to>`. It means that all actors whose name matches the `<from>` regex should receive the contact information of all actors whose name matches the `<to>` regex.

Note that in order to let two actors communicate, both of them should have the contact information of the other.

_Template only. Do not use it in a reproducible configuration._

#### `relationship_rules`

This property is used to configure relationships of actors in batches. It should be provided as a dictionary where each key is an actor name (or a regex matching multiple actors) and mapped to a dictionary of relationships. The actor name in a role instance identifier can be a regex matching multiple actors.

_Template only. Do not use it in a reproducible configuration._

#### `deployment_order`

Specifies which actor(s) should receive configuration deployment first, and in what order. Actors recorded in `profiles`, `profiles_separate` and `profiles_individual` that do not appear in this list will receive deployment last.

For example, given ten actors `a1` ~ `a10`, and the following deployment order:

```yaml
deployment_order:
  - a1
  - a4
  - a6
```

Then `a1` will receive deployment first, followed by `a4` and `a6`. Other actors will receive deployment after these three and in a random order. Note that this random order will _not_ be saved to a reproducible configuration file.

When writing a configuration template, you can use regex to match multiple actors. For example, given actors `a1` ~ `a10` and `b1` ~ `b10`, and the following deployment order:

```yaml
deployment_order:
  - a.*
  - b.*
```

Then actors `a1` ~ `a10` will receive deployment first, before `b1` ~ `b10`. The concrete order within each group will be determined randomly and recorded in a reproducible configuration. Therefore, a possible reproducible configuration will be:

```yaml
deployment_order:
  - a1
  - a4
  - a6
  - a9
  - ...
  - b3
  - b7
  - b5
  - ...
```

### Value Templates

You can use value templates in a configuration template to quickly configure multiple actors. A value template specifies the rule to generate configuration values for each actor matching a given regex. For example, consider the following configuration:

```yaml
roles:
  client.*:
    trainer:
      impl:
        dataset:
          class: src.dataset.MyDataset
          options:
            partition: $[1-10]
```

Here `$[1-10]` is a value template. It will be called for every actor whose name match the `client.*` regex to obtain a concrete value for the corresponding property (in this case, `partition`).

RoleML supports the following types of value template:

| Format | Value Generated per Call  | Possible Value Set for `client1` to `client20` |
|--|--|--|
| `$[1-10]` | The next number in a repeated iteration from 1 to 10. | 1, 2, ..., 10, 1, 2, ..., 10 |
| `@[1-10]` | A list containing all numbers between 1 and 10. | [1, 2, ..., 10] (for all clients) |
| `~[1-100, 4-11]` | A random value between 1 and 100, but excluding all numbers between 4 and 11. | 3, 17, 13, 16, 44, ... |
| `^[4, 11]` | A random value between 4 and 11. | 7, 4, 11, 10, 6, ... |
| `^[4, 22, 2]` | A random value in `range(4, 22, 2)`. | 8, 16, 10, 22, 4, ... |
| `^[6, 99, 3, 10]` | A list containing 10 values in `range(6, 99, 3)`. | [12, 81, 51, 33, ...], ... (different list per client) |
