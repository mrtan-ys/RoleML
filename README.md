# RoleML

Edge AI aims to enable distributed machine learning (DML) on edge resources to fulfill the need for data privacy and low latency. Meanwhile, the challenge of device heterogeneity and discrepancy in data distribution requires more sophisticated DML architectures that differ in topology and communication strategy. This calls for a _standardized and general programming interface and framework_ that provides support for easy development and testing of various DML architectures. Existing frameworks like FedML are designed for specific architectures (e.g. Federated Learning) and do not support users to customize new architectures on them.

RoleML is introduced as a novel, general-purpose **role-oriented programming model** for the development of DML architectures. RoleML breaks a DML architecture into a series of interactive components and represents them with a unified abstraction named _role_. Each role defines its behavior with three types of message _channels_, and uses _elements_ to specify the workloads in a modular manner and decouple them from the distributed training workflow. Powered by a runtime system, RoleML allows developers to flexibly and dynamically assign roles to different computation nodes, simplifying the implementation of complex architectures.

## Installation

You can install RoleML via pip (COMING SOON):

```shell
pip install roleml[grpc]
```

This will install dependencies for the gRPC communication backend. You can also install dependencies for the `http` backend, or both.

Alternatively, if you wish to customize the RoleML package, you can clone this repository and make an editable installation:

```shell
pip install -e path/to/roleml/source/directory[grpc]    # install dependencies for the gRPC backend
```

> For the complete list of supported extras, please check `pyproject.toml`.

For a minimal installation (without communication backend dependencies):

```shell
# pip installation
pip install roleml
# editable installation
pip install -e path/to/roleml/source/directory
```

### Extra Dependencies

To run the examples in the `examples` directory, `PyTorch` is required. Please refer to its [official website]((https://pytorch.org/get-started/locally/)) for installation commands.

To run the bundled profiling scripts, `viztracer` is required.

## Getting Started

* [Run a helloworld application](./docs/helloworld.ipynb) (requires Jupyter)
* [RoleML in 100 minutes](./docs/LEARN.ipynb) is a Jupyter notebook to help you learn RoleML while constructing a Federated Learning (FL) application.
* Also see the built-in examples in the `examples` directory. Besides FL, Gossip Learning (GL), E-Tree Learning (EL), and more are included.
* Detailed documents can be found in the `docs` directory.

## Changelog

See [CHANGELOG.md](./CHANGELOG.md).

## Middleware 2024 Artifact Evaluation

All documents are available in the `docs/experiments` directory.
