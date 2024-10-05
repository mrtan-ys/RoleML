# Deployment on Edge Devices

In this experiment, we further study the performance of RoleML on edge devices. All files required are in the Federated Learning example directory `<root>/examples/federated_learning`.

## Prerequisites

### Scripts that will be used

* `scripts/local_sgd.py` For local training
* `scripts/run.py` For running a single RoleML node
* `scripts/run_resource_with_stage_pauses.py` For running a single RoleML node and record the utilization of CPU and memory (a 5-second pause is added to the end of each stage, such as model loading, to distinguish between different stages)

### Configs that will be used

The configs will be used to run Federated Learning. All config files are in the `configs/dev` directory.

* `client-with-handshake.yaml` Config of a single client.
* `server-fedavg-with-handshake.yaml` Config of the server node (running FedAvg).

### Device Preparation

The original experiment is conducted using several Raspberry Pi 4Bs as edge devices. To verify functionality, other devices may also be used (or you could simply run all nodes on the same machine using different terminals).

* **RoleML installation**: See [here](0-preparation.md#roleml-package) for instructions.
* **Dataset preparation**: See [here](0-preparation.md#dataset) for instructions.

> `miniforge` is recommended for managing Python environments on Raspberry Pi.

## Local Training

1. Log into the testing device (e.g. using SSH).

2. `cd` to the _`scripts`_ directory.

3. Open `local_sgd.py` and change the dataset path (to the previously prepared _`<dataset-path>`_):

    ```python
    ...
    dataset_view = view_factory(
        MyCiFar10SlicedDataset(root='/path/to/dataset', index=0),
                                     # ^^^ change this to <dataset-path>
        converters=[transform_torch],
        batch_size=32, drop_last=False, combiner=combine)
    ...
    ```

4. Run **`local_sgd.py`** with the following arguments: **`-r -p -n 10 -d 2`**.

    * `-r` stands for resource utilization logging.
    * `-p` stands for adding a 5-second pause after every stage (such as model loading).
    * `-n 10` stands for 10 epochs.
    * `-d 2` stands for a maximum of 2 training threads.

5. After the script finishes successfully, a `resource.log` file should be available in the current directory, which records the resource utilization.

    > You may see a "No such file or directory" error when the script exits; this is normal and is because the Python script exits before the resource utilization logging script exits.

## Federated Learning

We use a simple topology with one client and one server. In the original experiment, the client is running on a Raspberry Pi while the server is running on a server in the same LAN.

1. Start the server

    a. Update the configuration in _`server-fedavg-with-handshake.yaml`_ as follows:

    ```yaml
    name: server
    address: 127.0.0.1:5000
     # ^^^ change to the expected address
     # (address that the server can be accessed through it in the future)
    ...
    roles:
      coordinator:
        impl:
          model:
            constructor_args:
              num_threads: 2
              # ^^^ the original experiment uses 2
          dataset: ...
          # ^^^ comment out this part since model testing is not needed
    ```

    b. Open a terminal, `cd` to the example root (_`<root>/examples/federated_learning`_) and run **`python scripts/run.py -c ./configs/dev/server-fedavg-with-handshake.yaml --src ./src`**. This will start a server node that is ready to receive client handshakes.

2. Start the client

    a. Update the configuration in _`configs/dev/client-with-handshake.yaml`_ as follows:

    ```yaml
    name: client1
    address: 192.168.2.1:5001
     # ^^^ change to the expected address
     # (address that the client can be accessed through it in the future)
    ...
    contacts:
      server: 192.168.2.2:5000
      # ^^^ change this to be consistent with the previously-configured server address
    ...
    roles:
      trainer:
        impl:
          model:
            constructor_args:
              num_threads: 2
              # ^^^ the original experiment uses 2
          dataset:
            constructor_args:
              dataset:
                options:
                  root: /path/to/dataset
                  # ^^^ change this to the <dataset-path> prepared before
    ```

    b. Open a terminal, `cd` to the example root (_`<root>/examples/federated_learning`_) and run **`python scripts/run_resource_with_stage_pauses.py -c ./configs/dev/client-with-handshake.yaml --src ./src`**. This will start a client node that automatically performs handshake with the server.

3. Train

    After completing previous steps, Federated Learning should start automatically. Simply wait for it to finish (the server terminal will prompt "FL is done"). A `resource.log` file that records the resource utilization should be available in the example root or the _`scripts`_ directory.
