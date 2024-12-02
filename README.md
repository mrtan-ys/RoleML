# RoleML

Edge AI aims to enable distributed machine learning (DML) on edge resources to fulfill the need for data privacy and low latency. Meanwhile, the challenge of device heterogeneity and discrepancy in data distribution requires more sophisticated DML architectures that differ in topology and communication strategy. This calls for a _standardized and general programming interface and framework_ that provides support for easy development and testing of various DML architectures. Existing frameworks like FedML are designed for specific architectures (e.g. Federated Learning) and do not support users to customize new architectures on them.

RoleML is introduced as a novel, general-purpose **role-oriented programming model** for the development of DML architectures. RoleML breaks a DML architecture into a series of interactive components and represents them with a unified abstraction named _role_. Each role defines its behavior with three types of message _channels_, and uses _elements_ to specify the workloads in a modular manner and decouple them from the distributed training workflow. Powered by a runtime system, RoleML allows developers to flexibly and dynamically assign roles to different computation nodes, simplifying the implementation of complex architectures. We further provide an automatic role offloading mechanism based on containerization to enhance the reliability of DML applications.

## Installation

You can install RoleML via pip:

```shell
pip install roleml-ai[starter]
```

The `[starter]` extra is recommended for beginners. This will include dependencies for the gRPC communication backend, as well as a profiling tool `viztracer` for performance analysis.

Other extras available include:

* __grpc__: support for gRPC communication backend.
* __http__: support for HTTP communication backend.
* __profiling__: a profiling tool named `viztracer`, which is required to run the bundled profiling helper scripts.
* __containerization__: support for containerized mode powered by Docker (requires Python 3.11 or higher).

Alternatively, if you wish to customize the RoleML package, you can clone this repository and make an editable installation:

```shell
pip install -e path/to/roleml/source/directory[grpc]    # + dependencies for gRPC backend
```

> The list of available extras may change. Please check `pyproject.toml` for any latest update.

For a minimal installation (without communication backend dependencies):

```shell
# PyPI installation
pip install roleml-ai
# editable installation
pip install -e path/to/roleml/source/directory
```

### Other Dependencies

To run the examples in the `examples` directory, `PyTorch` is required. Please refer to its [official website]((https://pytorch.org/get-started/locally/)) for installation commands.

## Getting Started

* [Run a helloworld application](./docs/helloworld.ipynb) (requires Jupyter)
* [RoleML in 100 minutes](./docs/LEARN.ipynb) is a Jupyter notebook to help you learn RoleML while constructing a Federated Learning (FL) application.
* Also see the built-in examples in the `examples` directory. Besides FL, Gossip Learning (GL), E-Tree Learning (EL), and more are included.
* Detailed documents can be found in the `docs` directory.

## Changelog

See [CHANGELOG.md](./CHANGELOG.md).

## Cite This Project

A technical paper describing the system is published on the Middleware 2024 conference. If you find this repository useful, please cite the paper in your work:

__Yuesheng Tan, Lei Yang, Wenhao Li, and Yuda Wu. 2024. RoleML: a Role-Oriented Programming Model for Customizable Distributed Machine Learning on Edges. In 24th International Middleware Conference (MIDDLEWARE ’24), December 2–6, 2024, Hong Kong, Hong Kong. ACM, New York, NY, USA, 13 pages. https://doi.org/10.1145/3652892.3700765__
