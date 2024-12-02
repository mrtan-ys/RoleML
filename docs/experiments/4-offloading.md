# Automic Role Offloading

This experiment measures efficiency of automatic role offloading using E-Tree learning.

## Prerequisites

This experiment requires a device to run VMs.

* **RoleML installation**: See [here](0-preparation.md#roleml-package) for instructions.
* **Dataset preparation**: See [here](0-preparation.md#dataset) for instructions.
* **Docker installation**: See [here](0-preparation.md#container-engine) for instructions.

You need to complete these steps on both the VM and the server.

Additionally, to make offloading work, you need to [install CRIU](https://criu.org/Installation) and enable the experimental feature in Docker. Please refer to the [CRIU documentation](https://criu.org/Docker) for instructions.

> Client1's VM are recommended to have at least 4 cores. Here we allocate 4 cores and 12GB memory to each VM.

> CRIU requires some kernel configurations. It is recommended to use a newer kernel version to avoid potential issues.

> Docker's intergration with CRIU still has some issues, which may cause the offloading to fail.

## E-Tree Learning

We will run E-Tree Learning with 6 clients, which will be deployed on the VM. Besides the client nodes, we also need another node to control the experiment, which will run a special role named Conductor. For simplicity, we will put this node on the server.


1. On each VM (running the clients)

    a. `cd` to example root _`<root>/examples/e_tree_learning`_.

    b. Update the configuration in _`configs/dev/client-offload.yaml`_ as follows:

    ```yaml
    name: client1
    # ^^^ change this to the expected name of the client
    address: 192.168.1.101:5000
    # ^^^ change to the expected address
    # (address that the client can be accessed through it in the future)
    ...
    contacts:
      conductor: 192.168.1.100:4000
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

    d. Open a terminal and run **`sudo <python-path> scripts/run.py -c ./configs/dev/client-offload.yaml --src ./src --containerize`**. This will start a client node that listens to the Conductor role for deployment and starting signal.

2. On the server (running conductor)

    a. `cd` to example root _`<root>/examples/e_tree_learning`_.

    b. Update the configuration in _`configs/dev/nodes/small-offload.yaml`_ as follows:

    ```yaml
    profiles:
      - name: client1 # running on the VM
        address: 192.168.1.101:5000
        # ^^^ change this to the expected address of client1
      - name: client2 # running on the VM
        address: 192.168.1.102:5000
        # ^^^ change this to the expected address of client2
      - name: client4 # running on the VM
        address: 192.168.1.103:5000
        # ^^^ change this to the expected address of client4
      ...do the same for the rest of the clients...
    ```

    d. modify `tests/conductor.py` to change the base class of the Conductor role to the containerization version:
    ```python
    # from roleml.library.roles.conductor.base import Conductor
    from roleml.extensions.containerization.roles.conductor.base import Conductor
    # ^^^ change the import statement to use the containerization version

    class ELConductor(Conductor):

        def __init__(self, name: str = 'EL'):
            super().__init__(name)
            self.cli.add_command('start', self.start, expand_arguments=True)
            # command template:
            # start --num-rounds 75

        def start(self, num_rounds: int = 75):
            self.call_task('coordinator', 'run', args={'num_rounds': num_rounds}).result()
    ```

    d. Open a terminal and run **`python tests/conductor.py --config tests/conductor-offload.yaml --workdir .`**. This will start a node to run the Conductor role, which is used to control the experiment with a runtime CLI (you should see a `EL>` prompt in the console).

3. Start training

    In the runtime CLI described above, run the following commands in order to start E-Tree Learning:

    ```
    configure configs/dev/appConfig-small-offload.yaml
    start --num_rounds 9999
    ```

4. Stress the root node's VM

    Open a new terminal on the VM and run:

    ```bash
    cat /dev/urandom | gzip -9 > /dev/null
    ```
    This will fully occupy a CPU core. Ideally, the 4-core-VM's CPU utilization should be around 400% now.

    If your VM has more than 4 cores, you can run this command multiple times to stress more cores, or change the threshold in the `tests/conductor-offload.yaml`->`roles.offloading_decider.options.threshold_ratio` to a lower value.

    Go to the terminal running the Conductor and wait at most 1 minute. You should see the Decider making decisions and Offloading Manager offloading the Coordinator role to the another node.