# Workloads

## Basic Usage

### Declaring and Using a Workload Element

A workload element is declared as a class attribute:

```python
class MyTrainer(Role):
    model = Element(TrainableModel)     # type: Element[TrainableModel]
    dataset = Element(Dataset)          # type: Element[Dataset]
```

The above declarations state that every instance of the `MyTrainer` role requires something typed `TrainableModel` and something typed `Dataset`, representing the model and the dataset, respectively. You can add [properties](#element-properties) while declaring an element to clarify its semantics or provide a default implementation.

> We recommend adding type annotations to better prevent programming errors.

After providing a role instance with an implementation of an element, an _element instance_ is available as an instance attribute of the role, whose name is the same as in declaration. Calling an element instance will return a workload object of the desired type:

```python
class MyTrainer(Role):  # continued
    @Task
    def train(self, caller, args, payloads):
        model = self.model()        # type: TrainableModel
        dataset = self.dataset()    # type: Dataset
        metrics = model.train(dataset, **args)
        return metrics
```

> Note that the role itself does not need to know where a workload object comes from. It can be constructed by a [constructor](#effective-constructor-and-arguments), or an [existing object](#impl).

It is possible to mark an implementation optional. To check if such an element has been implemented, you can check the `implemented` property:

```python
class MyTrainer(Role):  # continued
    dataset_test = Element(Dataset)

    @Task
    def apply_update(self, caller, args, payloads):
        model = self.model()
        update = payloads['update']
        model.set_params(update)
        # only perform model testing when a test set is available
        if self.dataset_test.implemented and isinstance(model, TestableModel):
            model.test(self.dataset_test())
```

> If a workload element is not implemented, we are actually accessing the corresponding class attribute, which by default returns `False` in availability check.

An element instance can be reset using the `reset()` API. This will remove any workload object cached by the instance. If a [destructor](#destructor) is available, it will be called with the object before removal to allow necessary cleanups. If a proper [constructor](#effective-constructor-and-arguments) is available, calling the element instance next time will produce a new workload object.

### Implementing a Workload Element

You can provide the implementation of a workload element for a role instance using the actor API `Actor.implement_element()`. Each element requires a separate API invocation.

The more flexible way is to provide the implementations via a configuration file. More detail can be found [here](../running-distributed-training/2-configuring-role.md#impl---workload-element-implementations).

## Properties

### Element Properties

Below are properties of a workload element typed `T`:

### `cls`

The expected type of workload objects (i.e. `T`). You can also specify other Python objects that can be used in instance check.

Note that a class specified in this property will NOT be used as the default constructor for constructing a workload object. To use the class as the default constructor, set the `default_constructor` property with it.

### `type_check`

Whether to enable type checking. When enabled, any constructed or loaded workload object must be a valid instance of `cls` (i.e. `isinstance(obj, cls)` must be True). If an instance also specifies the `class` property, then the workload object(s) created or loaded by that instance must also be valid instance(s) of `class`. Defaults to True (type checking is enabled).

### `optional`

Whether an implementation is optional when deploying an instance of the corresponding role. Defaults to False (i.e. an implementation is required). When an element is not optional but an implementation is not available to a role, a warning will be issued to the user.

If an implementation is not explicitly provided (e.g., via the `Actor.implement_element()` API or a configuration file), RoleML will try to make a default implementation out of the property values specified in declaration.

### Element Instance Properties

These properties are specified at the element instance level and contains the information about a concrete implementation of workload objects. However, you can still provide a default implementation while declaring the element using most of these properties with a `default` prefix to the property names. For example, a default constructor can be specified in the element via the `default_constructor` property.

### `class`

_Instance-level only. `cls` is the property for element declaration that has similar meanings._

Further specify (narrow down) the type of workload objects that are constructed or loaded. It is similar to the element's `cls` property in that a type specified here will also be used in type checking (if not disabled), but different in that it will also be used as the element instance's [effective constructor](#effective-constructor-and-arguments) for constructing workload objects when a [constructor](#constructor) is not otherwise provided.

### `constructor`

A callable that can be called with `constructor_args` to create a workload object. Again, the created object must be a valid instance of `cls` (and `class` of the element instance when provided) if type checking is not disabled.

The _effective constructor_ for an implementation is determined by the rule described [here](#effective-constructor-and-arguments).

### `constructor_args`

Keyword arguments that will be applied to the [effective constructor](#effective-constructor-and-arguments) when constructing a workload object.

The same constructor args will be used if there should be multiple constructions as determined by the [construction strategy](#construct_strategy).

Constructor args specified by an instance will not be merged with the default args provided in the declaration. For example, if the declaration provides a default value `{'a': 1, 'b': 2}`, and the implementation specifies `{'a': 3, 'c': 4}`, then the actual arguments used by the element instance will be `{'a': 3, 'c': 4}` (i.e. the key `b` will be ignored).

### `construct_strategy`

Controls the construction of workload objects in an element instance. There are three modes:

* `ONCE` (default): only construct once when calling the element instance and there is no available workload object. This constructed object will be cached for direct return in subsequent calls to the element instance.
* `ONCE_EAGER`: similar to `ONCE`, but the construction will be performed right after the corresponding role instance is deployed.
* `EVERY_CALL`: a new workload object will be created on every call to the element instance (and cached until the next call). The `reset()` API will be automatically called to remove the previously cached workload object.

Given the semantics of the `reset()` API, calling the element instance after resetting will always cause a new workload object to be created.

### `impl`

An object of type `T` that will be directly used as an available workload object and cached in the element instance. If the construction strategy is `ONCE` or `ONCE_EAGER`, this means that the constructor will never have a chance to be called unless `reset()` is used.

### `initializer`

A callable that when provided, will be invoked to initialize a workload object before it is returned to the caller of the element instance.

### `initialize_strategy`

Controls the use of the initializer (if provided). There are two modes:

* `ONCE`: a workload object is only initialized once after it has been constructed.
* `EVERY_CALL`: even when calling the element instance does not trigger a reconstruction, the existing workload object will still be re-initialized.

### `destructor`

A callable that will be called on the currently cached workload object when resetting the element instance or terminating the corresponding role instance. It can be used to perform some finalization such as file closing.

### `serializer`

A callable to serialize workload objects. The signature must be `(T, IOBase) -> None`. The file object should be managed by RoleML and therefore should not be manually closed.

The serialization will be automatically done if possible (i.e., if both `serializer` and `serializer_destination` are available) when the role instance is terminating. At other times, you can manually initiate a serialization process using the element instance's `serialize()` API and can customize the file to save the serialized workload object.

#### `serializer_mode`

The mode of the serializer, which corresponds to the mode to open a file for writing. Must be `text` for text mode or `binary` for binary mode. When specifying a serializer, it is strongly recommended to clarify its mode because the default mode specified by the element may not be desired.

### `serializer_destination`

_Instance-level only._

The path of the target file to save the currently cached workload object serialized by the serializer. The file will be opened and managed by RoleML when it is time to perform serialization.

### `deserializer`

A callable to deserialize a file to get a workload object. The signature must be `(IOBase) -> T`. The file object should be managed by RoleML and therefore should not be manually closed.

#### `deserializer_mode`

The mode of the deserializer, which corresponds to the mode to open a file for reading. Must be `text` for text mode or `binary` for binary mode. When specifying a deserializer, it is strongly recommended to clarify its mode because the default mode specified by the element may not be desired.

### `deserializer_source`

_Instance-level only._

The path of the target file from which the deserializer loads a workload object. The file will be opened and managed by RoleML when it is time to perform deserialization.

When a deserializer is available, a workload object will be loaded from the corresponding file given that [`impl`](#impl) is not provided. If the construction strategy is `ONCE` or `ONCE_EAGER`, this means that the constructor will never have a chance to be called.

### `implemented`

_Read only status variable._

A boolean value indicating whether a workload object is available or can be constructed by a valid effective constructor.

## Notes

### Effective Constructor and Arguments

Given a workload element (`element`) and its corresponding instance (`instance`) in a role instance, RoleML will search for an effective constructor in the following order:

1. `instance.constructor`
2. `instance.class`
3. `element.default_constructor`

For example, if the element has specified a default constructor (3), and the instance specifies the `class` property (2), the latter will be used as the effective constructor in subsequent construction(s) of workload object(s).

`element.cls` is _never_ used as the effective constructor, because it mainly serves the type checking purpose and some non-class symbols may be used in type checking. To use the class itself as the default constructor, set the `default_constructor` property with it.

The arguments to the effective constructor are `instance.constructor_args` or `element.default_constructor_args` if the former is missing. RoleML will not try to merge both if specified at the same time.

However, when calling the element instance, you can override the arguments. If any positional or keyword arguments are provided for the call, only these arguments will be passed to the effective constructor (unless there is already a workload object and the construction strategy does not support reconstruction).

> Dev note: any customized implementation of the element manager must also follow these rules.
