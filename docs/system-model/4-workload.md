# Workloads

[//]: # (This document contains one or more tables. A Markdown reader is recommended for better reading experience.)

## Basic Usage

### Declaring and Using a Workload Element

A workload element is declared as a class attribute:

```python
class MyTrainer(Role):
    model = Element(TrainableModel)     # type: Element[TrainableModel]
    dataset = Element(Dataset)          # type: Element[Dataset]
```

The above declarations state that every instance of the `MyTrainer` role requires something typed `TrainableModel` and something typed `Dataset`, representing the model and the dataset, respectively. You can add [properties](#element-properties-reference) while declaring an element to clarify its semantics or provide a default implementation.

> We recommend adding type annotations to better prevent programming errors.

After providing a role instance with an implementation of an element, an _element instance_ is available as an instance attribute of the role, whose name is the same as in declaration. This element instance is usually used by calling its `get()` API to obtain a workload object of the desired type:

```python
class MyTrainer(Role):  # continued
    @Task
    def train(self, caller, args, payloads):
        model = self.model.get()        # type: TrainableModel
        dataset = self.dataset.get()    # type: Dataset
        metrics = model.train(dataset, **args)
        return metrics
```

Note that the role itself does not need to know where a workload object comes from. This information is provided by the actual users of the DML architecture who configure the implementation. For example, it can be constructed from a factory function, or deserialized from a file on disk.

Alternatively, if you wish to set up the workload object before use, you can use the `initialize(...args)` API instead. It aims at returning a workload object at its initial state described by the args provided.

It is possible to mark an implementation optional. To check if such an element has been implemented, you can check the `implemented` property:

```python
class MyTrainer(Role):  # continued
    dataset_test = Element(Dataset, optional=True)

    @Task
    def apply_update(self, caller, args, payloads):
        model = self.model.get()
        update = payloads['update']
        model.set_params(update)
        # only perform model testing when a test set is available
        if self.dataset_test.implemented and isinstance(model, TestableModel):
            model.test(self.dataset_test())
```

See [this section](#advanced-usage) for more advanced use cases.

### Implementing a Workload Element

You can provide the implementation of a workload element for a role instance using the actor API `Actor.implement_element()`. Each element requires a separate API invocation.

The more flexible way is to provide the implementations via a configuration file. More detail can be found [here (configuration items)](#configuring-an-element-instance) and [here (configuration file format)](../running-distributed-training/2-configuring-role.md#impl---workload-element-implementations).

## Advanced Usage

### Element Instance APIs

A workload element instance consists of several core APIs with clear semantic. First of all, there are two APIs to produce ready-to-use workload objects:

* __`load()`__: load a workload object and return for direct use.
* __`initialize(args)`__: obtain a workload object at its initial state described by the args provided.

A workload element instance has an internal _buffer_ to store the workload object produced by the last call to any of these APIs. This allows you to can retrieve the same object multiple times by simply calling the __`get()`__ API. That also means if you call `load()` or `initialize(...)` again, the new object will replace the existing one in the buffer.

There are also two APIs operating on the workload object currently in the buffer:

* __`serialize()`__: serialize the workload object.
* __`unload()`__: remove the workload object from the buffer, and perform any necessary cleanup actions (e.g., closing opened files). This API will also be effectively called when a new workload object is to occupy the buffer (e.g., when `load()` or `initialize(...)` is called).

Besides, the following properties can be accessed to check in advance if calling certain APIs will succeed:

* `implemented`: whether a workload object can be provided for use. That is, it checks to see if the instance has implemented the action for either `load()` or `initialize(...)`, or has a default workload object implementation in element declaration (i.e., [`default` or `default_factory` property](#default-default_factory)).
* `serializable`: whether it is possible to serialize workload objects. Recommended to access before calling `serialize()` as an exception will be raised if there is no buffered object or the serializer is missing.

### Configuring an Element Instance

When instantiating a role, calls to the core APIs mentioned above (`load()`, `initialize(...)`, `serialize()`, `unload()`) rely on proper configurations associated with concrete workloads. Each of these APIs corresponds to a configuration item, which specifies a method to achieve the API's intent. These methods are named _loader_, _initializer_, _serializer_, and _unloader_, respectively.

Each of these configuration items has the following structure:

* `method`: name of the method, which is effectively a function to be called inside the API.
* Other args: will be used to configure the method.

> Note that the `get()` API will attempt to fetch an workload object in the following order: (1) buffer; (2) loader; (3) `element.default_factory()`; (4) `element.default`. The initializer is not considered as this is fixed to a no-arg call.

RoleML runtime supports the following built-in methods:

[//]: # (DO NOT FORMAT THIS TABLE SINCE IT WILL MAKE IT UGLIER; USE A MARKDOWN READER)

| Method Type | Method Name | Description | Args |
| ----------- | ----------- | ----------- | ---- |
| Loader | `direct-use` | Use the object directly specified. Suitable for configuration via code instead of text file. | `target` -- the desired object |
| Loader | `direct-import` | Use the object imported from the path specified. For example, `"foo.BAR"` means to import `BAR` from module `foo`. | `target` -- the import path |
| Loader | `factory` | Use the specified factory function to construct a workload object. | `target` -- the factory object or its import path <br> `args` -- arguments to be passed to the function, which should be JSON-serializable for maximum compatibility |
| Loader | `pickle` | Use `pickle` to deserialize a binary file for a workload object. | `target` -- path of the file |
| Loader | `json` | Use `json` to deserialize a text file for a workload object. | `target` -- path of the file |
| Initializer | `basic` | Use a custom function as the initializer. The function should accept `None` or the currently-buffered workload object as its first argument (i.e., before any other arguments provided by in-role API call), which provides an opportunity to reuse an existing object if possible. | `target` -- the function object or its import path |
| Initializer | `factory` | Use a factory function as the initializer to construct a new workload object on API call. This factory should be able to accept args provided via the API call. | `target` -- the factory object or its import path
| Serializer | `pickle` | Use `pickle` to serialize workload objects. | `target` -- path of the binary file to save the pickled object to <br> `base` -- required parent class of any workload object to be eventually pickled (if a workload object is not an instance of `base`, serialization will be skipped) |
| Serializer | `json` | Use `json` to serialize workload objects. | `target` -- path of the text file to save the serialized object to <br> `base` -- required parent class of any workload object to be eventually pickled (if a workload object is not an instance of `base`, serialization will be skipped) |
| Unloader | `basic` | Use a custom function as the unloader. | The function should the currently-buffered workload object as its first argument (no need to consider `None`). | `target` -- the function object or its import path |

Additionally, you can set a special configuration item `eager_load` to True to indicate that the loader should be called to prepare a workload object as early as when the role is being deployed. This helps to improve performance or foster fair comparison between DML architectures in some cases. Note that this does not apply to the initializer as it relies on in-role arguments to work.

### Customizing Element API Methods

It is possible to provide your own methods. All you need is to register your customize method to the corresponding registry in `roleml.core.builders.element` before the actor loads configuration.

## Element Properties Reference

Below are properties of a workload element typed `T`:

### `cls`

The expected type of workload objects (i.e., `T`).

### `default`, `default_factory`

Provide default workload object implementation. `default` should be an instance of `T`, while `default_factory` should be a no-arg function returning an instance of `T`. When both properties are specified, `default_factory` will prevail in workload object retrieval when necessary.

### `default_initializer`

Initializer method to be used for the `initialize(...)` API when no initializer is configured.

### `type_check`

Whether to enable type checking. When enabled, any workload object produced by `load()` or `initialize(...)` will be examined to see whether it is a valid instance of the desired type. Defaults to False (i.e., type checking is disabled).

See also [`type_check_fallback`](#type_check_fallback).

### `type_check_fallback`

A fallback type to be used for type check of workload objects when `cls` cannot be used in `isinstance()` (e.g., a parameterized `Callable`). Only used when `type_check` is set to True.

### `optional`

Whether an implementation is optional when deploying an instance of the corresponding role. Defaults to False (i.e. an implementation is required). When an element is not optional but an implementation is not available to a role (property `implemented` of element instance evaluated to False), the whole role instance will be deemed unusable and attempting to add the role instance to an actor will result in failure.

If an implementation is not explicitly provided (e.g., via the `Actor.implement_element()` API or a configuration file), RoleML will try to make a default implementation out of the property values specified in declaration.

### `require_serializable`

Requires that a serializer must be provided. If the serializer is missing, the whole role instance will be deemed unusable and attempting to add the role instance to an actor will result in failure. Defaults to False.
