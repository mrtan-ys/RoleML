# Running Actor(s)

## Running via Script

RoleML ships with several scripts that can help you start one or more nodes (actors) from the command line easily.

### Basic Scripts

The following scripts can be imported from `roleml.scripts.runner`:

* To run a single actor, please refer to `single.run_actor_from_cli()`.
* To run a batch of actors, please refer to `batch.run_actors_from_cli()`.

These CLI scripts also provide options to enable and customize profiling, which will record the time of every function and method calls. This feature is based on `viztracer`, so make sure it is installed in your environment.

### Recipes

RoleML also provides some additional scripts that add extra functionalities to the original CLI for running a single actor. These scripts can be imported from `roleml.scripts.runner.recipes`. Below is a brief introduction of them:

* `measurement.resource.run.run_with_resource_measurements()`: measure the usage of CPU and memory while running an actor. The sampling period is 0.5 seconds and the result will be saved to `resource.log` in the working directory.
* `measurement.temperature_rpi.run.run_with_temperature_rpi_measurements()` (for Raspberry PI): measure the CPU temperature of the RPI device while running an actor for a given period of time and save the result to `temperature_rpi.log` in the working directory.

### Usage

In your own application, import the script you need and run it with corresponding command-line arguments:

```python
# app.py
from roleml.scripts.runner.single import run_actor_from_cli

if __name__ == '__main__':
    run_actor_from_cli()
```

```shell
python app.py --workdir . --config config.yaml --src ./src
```

Check the original script for more detail about accepted arguments, including the ones for profiling.

## Running via Raw Code

You can also start an actor using raw code. Instead of constructing an actor from scratch, we recommend using an actor builder to create it. The configuration can be loaded from a dict (accepting the [same format](1-configuring-node.md) as a configuration file), or you can directly set the attributes of the builder.

The actor builder used by default can be imported from `roleml.core.actor.default.bootstrap`.

When running an actor manually, it is your responsibility to manage the behavior at program exit.

> Dev note: each customized actor class should be paired with a separate actor builder class.
