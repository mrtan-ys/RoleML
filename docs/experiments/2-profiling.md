# Execution Time Profiling

In this experiment, we study the time overhead of RoleML components in different use cases.

This experiment involves two architectures: Federated Learning and Gossip Learning. You can find their implementation in _`<root>/examples/{federated_learning, gossip_learning}`_.

## Prerequisites

This experiment requires two devices: one is used to run the VM, which contains a single node to be profiled, and the other (typically a server) to run all other nodes in the topology.

* **RoleML installation**: See [here](0-preparation.md#roleml-package) for instructions.
* **Dataset preparation**: See [here](0-preparation.md#dataset) for instructions.

You need to complete these steps on both the VM and the server.

> For the VM to be able to communicate with the external server, the virtual network adapter needs to run in bridge mode, and the IP address (also subnet mask, gateway) needs to be manually configured.

> The original experiment requires the VM to have sufficient RAM. For functionality checks, however, 4GB or lower should be acceptable.

## Federated Learning

For simplicity without affecting the result fidelity, we apply a one-client-one-server topology where the client is deployed on the VM.

1. Start the server

    a. On the server, `cd` to example root _`<root>/examples/federated_learning`_.

    b. Update the configuration in _`configs/dev/server-fedavg-with-handshake.yaml`_ as follows:

    ```yaml
    name: server
    address: 192.168.2.2:5000
     # ^^^ change to the expected address
     # (address that the server can be accessed through it in the future)
    ...
    roles:
      coordinator:
        impl:
          dataset: ...
          # ^^^ comment out this part since model testing is not needed
    ```

    c. Open a terminal and run **`python scripts/run.py -c ./configs/dev/server-fedavg-with-handshake.yaml --src ./src`**. This will start a server node that is ready to receive client handshakes.

2. Start the client

    a. On the VM, `cd` to example root _`<root>/examples/federated_learning`_.

    b. Update the configuration in _`configs/dev/client-with-handshake.yaml`_ as follows:

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

    c. Open a terminal and run **`python scripts/run.py -c ./configs/dev/client-with-handshake.yaml --src ./src -p -pe 3000000`**. This will start a client node that automatically performs handshake with the server, and a profiler that automatically records the execution time of each Python function.

    > For functionality checks, the number of trace entries (`-pe`) may be reduced when the memory is constrained.

3. Train

    After completing previous steps, Federated Learning should start automatically. Simply wait for it to finish (the server terminal will prompt "FL is done"). The trace file should be available in the _`profiling`_ directory in the example root. It can be opened with `vizviewer` in the current environment.

    > A new run will overwrite the existing trace file. So please rename or move it if you want to keep a trace file.

## Gossip Learning (process mode)

We will run Gossip Learning with three clients, one of which will be deployed on the VM for profiling, while the other two will be deployed on the server. Besides the client nodes, we also need another node to control the experiment, which will run a special role named Conductor. For simplicity, we will also put this node on the server.

1. On the VM (running the client to be profiled)

    a. `cd` to example root _`<root>/examples/gossip_learning`_.

    b. Update the configuration in _`configs/dev/client.yaml`_ as follows:

    ```yaml
    name: client1
    address: 192.168.2.1:5001
     # ^^^ change to the expected address
     # (address that the client can be accessed through it in the future)
    ...
    contacts:
      conductor: 192.168.2.2:4000
      # ^^^ change this to the expected address of the control node (running the Conductor role)
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
          dataset_test:
            constructor_args:
              dataset:
                options:
                  root: /path/to/dataset
                  # ^^^ change this to the <dataset-path> prepared before
    ```

    c. Open a terminal and run **`python scripts/run.py -c ./configs/dev/client.yaml --src ./src -p -pe 3000000`**. This will start a client node that listens to the Conductor rode for a starting signal.

2. On the server (running all other nodes)

    a. `cd` to example root _`<root>/examples/gossip_learning`_.

    b. Update the configuration in _`configs/dev/nodes/small-overhead.yaml`_ as follows:

    ```yaml
    profiles:
    - name: client2     # running on server
      address: 192.168.2.2:5002
      # ^^^ change this to the expected address of client2
    - name: client3     # running on server
      address: 192.168.2.2:5003
      # ^^^ change this to the expected address of client3

    profiles_separate:
    - name: client1     # running on the VM
      address: 192.168.2.1:5001
      # ^^^ change this to the expected address of client1
    ```

    c. Update the configuration in _`configs/dev/roles/default.yaml`_ as follows:

    ```yaml
    client.*:   # node name (RegEx)
      trainer:  # role instance name
        impl:
          dataset:
            constructor_args:
              dataset:
                options:
                  root: /path/to/dataset
                  # ^^^ change this to the <dataset-path> prepared before
          dataset_test:
            constructor_args:
              dataset:
                options:
                  root: /path/to/dataset
                  # ^^^ change this to the <dataset-path> prepared before
    ```

    d. Open a terminal (A) and run **`python tests/run_batch.py configs/dev/nodes/small-overhead.yaml --workdir . --src ./src --common-config configs/dev/shared/common.yaml`**. This will start `client2` and `client3` on the current server.

    e. Open another terminal (B) and run **`python tests/conductor.py --config tests/conductor.yaml --workdir .`**. This will start a node to run the Conductor role, which is used to control the experiment with a runtime CLI (you should see a `GL>` prompt in the console).

3. Train

    In the runtime CLI described above, run the following commands in order to start Gossip Learning:

    ```
    configure configs/dev/appConfig-small-overhead.yaml
    start --num_rounds 5
    ```

    Wait until the training finishes (no more log messages about training progress in the terminals), then simply kill the scripts. (You may need to use Ctrl+C multiple times to kill the control node). When killing the client on the VM, wait while the profiler is dumping the traces. The trace file should be available in the `profiling` directory in the example root. It can be opened with `vizviewer` in the current environment.

    > A new run will overwrite the existing trace file. So please rename or move it if you want to keep a trace file.

## Gossip Learning (containerized mode)

We will run Gossip Learning with three clients, which will be deployed on the VM, while one of them is used for profiling. Besides the client nodes, we also need another node to control the experiment, which will run a special role named Conductor. For simplicity, we will put this node on the server.


1. On each VM (running the clients)

    a. `cd` to example root _`<root>/examples/gossip_learning`_.

    b. Update the configuration in _`configs/dev/client-containerized.yaml`_ as follows:

    ```yaml
    name: client1
    # ^^^ change this to the expected name of the client
    address: 10.184.102.225:5000
    # ^^^ change to the expected address
    # (address that the client can be accessed through it in the future)
    ...
    contacts:
      conductor: 10.184.102.1:4000
      # ^^^ change this to the expected address of the control node (running the Conductor role)
    ...
    base_image: python:3.11.10-bullseye
    # ^^^ change this to the desired Python version
    #     see https://hub.docker.com/_/python/
    #     had better be same as the RoleML environment
    mounts: [
      "/path/to/dataset/on/vm:/path/to/dataset/in/container",
      # ^^^ change the former path to <dataset-path>
      #     change the latter path to what you have configured in the `configs/dev/roles/default.yaml`->`client.*`->`trainer`->`dataset`->`constructor_args`->`dataset`->`options`->`root`
      "/path/to/RoleML/on/vm:/roleml" # mount roleml source code into container
      # ^^^ change the former path to <root>
    ]
    temp_dir: /tmp
    # ^^^ change this to a writable directory on the vm   
    ```

    c. Run `which python` to get the path of the Python executable, denoted as _**`<python-path>`**_.

    d. Open a terminal and run **`sudo <python-path> scripts/run.py -c ./configs/dev/client-containerized.yaml --src ./src -p -pe 3000000 --containerize`**. This will start a client node that listens to the Conductor role for deployment and starting signal.

2. On the server (running conductor)

    a. `cd` to example root _`<root>/examples/gossip_learning`_.

    b. Update the configuration in _`configs/dev/nodes/small-overhead-containerized.yaml`_ as follows:

    ```yaml
    profiles:
      - name: client1 # running on the VM
        address: 10.184.102.225:5000
        # ^^^ change this to the expected address of client1
      - name: client2 # running on the VM
        address: 10.184.102.104:5000
        # ^^^ change this to the expected address of client2
      - name: client3 # running on the VM
        address: 10.184.102.125:5000
        # ^^^ change this to the expected address of client3
    ```

    d. Open a terminal and run **`python tests/conductor.py --config tests/conductor.yaml --workdir .`**. This will start a node to run the Conductor role, which is used to control the experiment with a runtime CLI (you should see a `GL>` prompt in the console).

3. Train

    In the runtime CLI described above, run the following commands in order to start Gossip Learning:

    ```
    configure configs/dev/appConfig-small-overhead-containerized.yaml
    start --num_rounds 5
    ```

    Wait until the training finishes (no more log messages about training progress in the terminals), then simply kill the scripts. (You may need to use Ctrl+C multiple times to kill the control node). 
    
    When killing the client on the VM, wait while the profiler is dumping the traces. It may take a few time and **DO NOT** press Ctrl+C again until all the roles exited, otherwise the trace file will be empty.
    
    The trace file should be available in the `profiling` directory in the example root. It can be opened with `vizviewer` in the current environment.
