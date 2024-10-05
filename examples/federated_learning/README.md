# Federated Learning Quickstart

This guide will lead you through the process of running the Federated Learning example, where we use the local machine to simulate multiple computation nodes.

## Prepare the Environment

RoleML is developed with Python 3.10. We expect the minimal version to run RoleML to be >= 3.9.

1. Install RoleML if you have not done it yet. For this example, we also need `torch`, `torchvision` and `numpy`. Please refer to [PyTorch's official website](https://pytorch.org/get-started/locally/) for the best commands to install them.

2. Download the [official CIFAR-10 dataset](https://www.cs.toronto.edu/~kriz/cifar-10-python.tar.gz) and extract it somewhere.

3. Go to the root of the Federated Learning project: `examples/federated_learning` (referred to as `<fl-root>` below).

4. Split the CIFAR-10 dataset using the script `<fl-root>/src/federated_learning/workload/cifar10_splitter.py`. Note that the output directory (where the dataset slices are stored) and the testing set directory (the original `test_batch` file) are needed by the following configurations in order to load the corresponding data files.

## Configure

The nodes to run FL can be started individually or in a batch. To conduct an FL experiment, we usually prefer the latter.

The configuration files for the FL application is located at `<fl-root>/configs/dev`. Each of the `appConfig-*.yaml` files can be considered as a "recipe" with specific configurations for the roles, nodes, etc. Let's take `appConfig-fedavg-medium.yaml` as an example, where different parts of the configuration are included as links to the separate YAML files. (RoleML extends the YAML format to support file inclusion.)

The most common fields of an application config are:

* `profiles`: names and network addresses of the nodes.
* `roles`: role assignment configuration for every node. RegEx is supported to match multiple nodes and apply the same configuration at the same time. Value templates are supported to fine-tune every individual node in a batch.
* `relationships`: relationship configuration of each node.
* `relationship_rules`: relationship patterns, which will be converted into relationship configurations.
* `relationship_links`: can be used to create aliases for a given relationship.
* `connection_rules`: defines the list of nodes that are visible to each node in network communication.

The minimal configurations you need to modify include the dataset paths. If you don't modify the network addresses, all nodes will run on different ports on `127.0.0.1`. However, if you modify them, you will need to install RoleML and start the nodes on the corresponding machine(s) later.

Meanwhile, `client.yaml` contains a full example to start an individual FL client. In real-world deployment, you can copy this configuration to each client (with some on-demand adjustments such as node name and network address) and start an actor on it.

The source code of the roles are in `<fl-root>/src`. You can check them to see how roles are written in RoleML. The workloads (model, dataset and processing functions) are also in this directory.

## Run

We will run an FL experiment using the scripts in `<fl-root>/tests`:

1. Go to the project directory `<fl-root>`.

2. Open a terminal (A) and run **`python tests/run_batch.py configs/dev/nodes/medium.yaml --workdir . --src ./src --common-config configs/dev/shared/common.yaml`**. This will start a batch of "raw" nodes including 10 clients and 1 server (defined in `<fl-root>/configs/dev/nodes/medium.yaml`). Each node is represented by an actor.

   > If you have configured the nodes to run on a different machine, install RoleML and start the nodes on that machine instead.

3. When the nodes are started (shouldn't take too long), they are ready to accept role assignments and other configurations from an external role named `Conductor`. This role will be started in a separate actor, and you can configure the startup options of it in `<fl-root>/tests/conductor.yaml`. In the role definition file (`<fl-root>/tests/conductor.py`), you can edit the entrypoint function of distributed training. In this example, it will call the task channel on the `Coodinator` role.

4. Open another terminal (B) and run **`python tests/conductor.py --config tests/conductor.yaml --workdir .`**. This will start an actor to run the Conductor role, which will then open a CLI for user control via the console.

5. In the Conductor CLI (a prompt `FL>` should be visible), run the command **`configure configs/dev/appConfig-fedavg-medium.yaml`** to deploy the configuration file. Every deployment generates a separate reproducible configuration (named `run-*.yaml`).

6. After the deployment is completed, you will see a prompt in the Conductor terminal. If the deployment gets stuck (check terminal A), simply kill (Ctrl+C) the scripts in both terminals and start the test again. (If possible, use Ctrl+D (EOF) instead for terminal B to stop the conductor gracefully.)

7. In the Conductor CLI, run the command **`start`** to initiate a DML run. You can also provide extra arguments originally defined in `conductor.py`, just like how they will be accepted by an `argparse` argument parser. In this example, a possible command with arguments is `start --num_rounds 20 --select-ratio 0.5`, which means the FL run will last for 20 rounds and 50% of the clients will be selected in each round.

8. Check the outputs of terminal A and wait for the FL run to finish (you should see something like `FL is done`). Then, exit by Ctrl+C for terminal A and Ctrl+D for terminal B (running the Conductor). The logs will be saved to `logs/<start-time>`.

## What's Next?

RoleML is a flexible programming model for distributed training. Feel free to customize the Federated Learning implementation, or check other examples provided by us, including Gossip and E-Tree Learning.

Meanwhile, [RoleML in 100 minutes](../../docs/LEARN.ipynb) is a Jupyter notebook that will lead you through the complete process of developing a DML architecture and running an application.
