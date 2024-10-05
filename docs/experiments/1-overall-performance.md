# Overall Training Performance

This experiment measures the time cost for RoleML to complete a FL run with varied numbers of clients.

## Prerequisites

We will run all nodes on a single machine (server recommended).

* **RoleML installation**: See [here](0-preparation.md#roleml-package) for instructions.
* **Dataset preparation**: See [here](0-preparation.md#dataset) for instructions.

## Running in Process Mode

The root of the example is _`<root>/examples/federated_learning`_. In the following, we will use _**`<fl-root>`**_ to represent this directory.

1. `cd` to `<fl-root>`.

2. Update the configuration in _`configs/dev/roles/fedavg-v2-with-registration.yaml`_ as follows:

    ```yaml
    client.*:
      trainer:
        impl:
          model:
            constructor_args:
              num_threads: 1
              # ^^^ the original experiment uses 1
          dataset:
            constructor_args:
              dataset:
                options:
                  root: /path/to/dataset
                  # ^^^ change this to the <dataset-path> prepared before
    server:
      coordinator:
        impl:
          model:
            constructor_args:
              num_threads: 4
              # ^^^ the original experiment uses 4
          dataset:
            constructor_args:
              dataset:
                options:
                  root: /path/to/dataset
                  # ^^^ change this to the <dataset-path> prepared before
    ```

3. By default, all nodes are running on `127.0.0.1`. So there is no need to change the nodes' addresses. However, if you encounter problems like _address already in use_, you may want to change the ports used by the clients in _`configs/dev/nodes/medium.yaml`_.

4. Open a terminal (A) and run **`python tests/run_batch.py configs/dev/nodes/medium.yaml --workdir . --src ./src --common-config configs/dev/shared/common.yaml`**. This will start a batch of "raw" nodes including 10 clients and 1 server (defined in `<fl-root>/configs/dev/nodes/medium.yaml`). Each node is represented by an actor.

5. When the nodes are started (shouldn't take too long), they are ready to accept role assignments.

6. Open another terminal (B) and run **`python tests/conductor.py --config tests/conductor.yaml --workdir .`**. This will start another actor to run the Conductor role (used to configure other nodes), which will then open a CLI for user control via the console.

    > This actor will run on port 4000 by default. If this port has been occupied, change to another port by configuring _`tests/conductor.yaml`_ and _`configs/dev/shared/common.yaml`_.

7. In the Conductor CLI (a prompt `FL>` should be visible), run the command **`configure configs/dev/appConfig-fedavg-v2-medium-with-registration.yaml`** to deploy the configuration file. Every deployment generates a separate reproducible configuration (named `run-*.yaml`).

8. After the deployment is completed, Federated Learning should start automatically.

9. Check the outputs of terminal A and wait for the FL run to finish (you should see something like `FL is done`). Then, exit by Ctrl+C for terminal A and Ctrl+D for terminal B (running the Conductor). The logs will be saved to `logs/<start-time>`.

## Running in Containerized Mode

1. `cd` to `<fl-root>`.

2. Update the configuration in _`configs/dev/shared/common-containerized.yaml`_ as follows:

    ```yaml
    base_image: python:3.11.10-bullseye
    # ^^^ change this to the desired Python version
    #     see https://hub.docker.com/_/python/
    #     had better be same as the RoleML environment
    mounts: [
      "/path/to/dataset/on/host:/path/to/dataset/in/container",
      # ^^^ change the former path to <dataset-path>
      #     change the latter path to what you have configured in the `configs/dev/roles/fedavg-v2-with-registration.yaml`->`client.*`->`trainer`->`dataset`->`constructor_args`->`dataset`->`options`->`root`
      "/path/to/RoleML:/roleml" # mount roleml source code into container
      # ^^^ change the former path to <root>
    ]
    temp_dir: /tmp
    # ^^^ change this to a writable directory on your host    
    ```

3. Run `which python` to get the path of the Python executable, denoted as _**`<python-path>`**_.

4. Open a terminal (A) and run **`sudo <python-path> tests/run_batch.py configs/dev/nodes/medium.yaml --workdir . --src ./src --common-config configs/dev/shared/common-containerized.yaml --containerize`**.

5. Open another terminal (B) and run **`python tests/conductor.py --config tests/conductor.yaml --workdir .`**.

6. In the Conductor CLI (a prompt `FL>` should be visible), run the command **`configure configs/dev/appConfig-fedavg-v2-medium-with-registration-containerized.yaml`** to deploy the configuration file.

7. After the deployment is completed, Federated Learning should start automatically.

8. Check the outputs of terminal A and wait for the FL run to finish (you should see something like `FL is done`). Then, exit by Ctrl+C for terminal A and Ctrl+D for terminal B (running the Conductor). The logs will be saved to `logs/<start-time>`.
