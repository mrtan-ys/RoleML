# General Preparation

RoleML is designed to be compatible with Python 3.9 or above. We recommend to install RoleML and all required packages in a separate environment.

## RoleML Package

For efficient conduction of experiments, we recommend making an editable installation of RoleML:

1. Clone the repository and **`cd`** to the root of the repository.
2. Install RoleML with **`pip install -e .[grpc,profiling,containerization]`**. This will install RoleML and dependencies for the gRPC communication backend, profiling and containerization in the current environment.

We will use _**`<root>`**_ to represent the root directory of the repository.

## Model

The model used (LeNet-5 RGB) is developed with PyTorch. We recommend installing the latest version of PyTorch using the following command:

```shell
# for pip
pip3 install torch torchvision --index-url \
    https://download.pytorch.org/whl/cpu
# for conda
conda install pytorch torchvision cpuonly -c pytorch
```

## Dataset

All experiments are conducted using the CIFAR-10 dataset. Please download it from the [official website](https://www.cs.toronto.edu/~kriz/cifar-10-python.tar.gz) and extract the archive somewhere. Then, we need the script `<root>/roleml/library/workload/datasets/zoo/image/cifar_10/splitter.py` to split the training set. Please run this script as

```shell
python splitter.py \
    <path/of/cifar-10-batches-py> <path/to/save/outputting/slices>
```

In the following experiments, we will be using the sliced training set (`data_x.npy` and `labels_x.npy` where `x` ranges from 0 to 24) and the original `test_batch`. For convenience, put all these files in a single directory, which will be referred to as _**`<dataset-path>`**_ later.

## Container Engine

RoleML supports containerization of roles. To enable containerized mode, please install Docker engine following the instructions on the [official website](https://docs.docker.com/get-docker/). (Currently, RoleML only supports Docker as the container engine.)
