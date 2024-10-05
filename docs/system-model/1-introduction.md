# Introduction

## About Distributed Machine Learning (DML)

Edge AI aims to enable **distributed machine learning (DML)** on edge resources to fulfill the need for data privacy and low latency. Meanwhile, the challenge of device heterogeneity and discrepancy in data distribution requires more sophisticated _DML architectures_ that differ in topology and communication strategy. A DML architecture defines how distributed computation nodes collaborate to speed up a model training job. For example, **Federated Learning** is an architecture that leverages a centralized topology, where a global server aggregates model updates produced by different training clients, usually in a synchronous manner. On the other hand, **Gossip Learning** is a fully distributed, asynchronous architecture in which every client trains its model and propagates updates in its own pace.

## Limitations on Existing DML Systems

Existing DML systems for edge computing (such as FedML, FedScale, and Flower) mostly target Federated Learning and adopt the node-oriented programming model (i.e. program for individual nodes). This approach is unsuitable for general DML development. In modern DML architectures, it is common to assign multiple responsibilities to a single computation node. For example, many decentralized architectures assign aggregation to some training nodes to support localized aggregation. Such assignment may also change over time when the node capability changes. Traditional programming models require developers to define all functionalities in one place, which often leads to repetitive and complicated coding and is hard to maintain or extend. 

## RoleML: Role-Oriented DML Development

In RoleML, we solve this problem by breaking a DML architecture into more fine-grained interactive components and using _roles_ to express them uniformly.

Roles are functional components that interact with each other within a DML architecture. The rule of thumb in development is that _each role should only have one responsibility_. For example, at the server side of Federated Learning, it is recommended to define a role for aggregation and another separate role for client selection. Since FL is not a strictly fixed pattern, more roles can be added if your FL variant introduces extra features, such as client clustering.

RoleML unifies the formats of intra- and inter- node communication, so that you can freely assign roles to different physical nodes without worrying about their interaction. This enables a new process for DML development: designing individual modules that logically build up a DML architecture, and _constructing nodes in a building block fashion_ at runtime, which greatly improves flexibility.

> Note: in subsequent documents, we will use the term "actor" and "node" interchangeably. An actor is mainly a runtime concept. Each RoleML process will create an actor object to hold the roles, while each physical node typically runs one RoleML process in a DML application (unless in a simulation or experimental environment), which means one actor per node.
