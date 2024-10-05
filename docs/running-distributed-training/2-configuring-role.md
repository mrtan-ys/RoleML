# Writing the Configuration of a Role

When starting an actor, you may also want to configure the roles that should be run on it. The recommended way to start an actor is by providing a configuration file to the [launching script](./4-running-actor.md#running-via-script). In a configuration file, each role is specified as a dictionary with the keys described [as follows](#configuration-keys).

## Configuration Keys

### `class` - The Role Class

The role class to instantiate a role. In a configuration file, you can specify a fully qualified name of the role class (such as `src.roles.MyRole`), and RoleML will automatically import the class.

### `options` - Constructor Arguments

A dictionary containing (keyword) arguments that will be used when creating a role instance. If you have defined parameters for the role class's `__init__()` method, you can provide arguments for them here.

> For the sake of compatibility, parameters defined in the `__init__()` method should only accept JSON-compatible data types, such as `int`, `str`, or `list`.

### `impl` - Workload Element Implementations

A dictionary containing implementations of each workload element. For each entry, the key is the name of the element, and the value is the actual implementation. See [here](../system-model/4-workload.md#element-instance-properties) for the full list of properties of an implementation.

## Example

Assume we have the following role class in `src/roles/trainer.py`:

```python
class MyTrainer(Role):
    
    def __init__(self, default_num_epochs: int = 1):
        self.default_num_epochs = default_num_epochs
        ...

    model = Element(TrainableModel)     # assume TrainableModel is an interface
    dataset = Element(Dataset)          # assume Dataset is an interface

    ...
```

A possible configuration for adding a role of this class will be:

```yaml
class: src.roles.trainer.MyTrainer
options:
  default_num_epochs: 2
impl:
  model:
    class: src.workloads.model.MyModel
    constructor_args:
      lr: 0.01
  dataset:
    class: src.workloads.dataset.MyDataset
    constructor_args:
      root: /path/to/my/dataset
      part: 2
```

With the above configuration, a model object will be created as `MyModel(lr=0.01)` when calling the corresponding element instance for the first time. Since the construction strategy defaults to `ONCE`, the created model object will be cached and directly returned in subsequent calls to the same element.
