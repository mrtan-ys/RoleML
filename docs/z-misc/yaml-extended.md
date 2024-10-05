# Extended YAML Format

RoleML supports an extended YAML format, which allows file inclusion. With this feature, you can separate a full configuration into several files and change each part individually. It is especially useful if you need to experiment with different but similar setups.

## Usage

To demonstrate the use, the following source file (`a.yaml`) will be used across examples:

<span id="a"></span>

```yaml
one: two
three: four
five:
  six:
    seven: eight
    nine: ten
```

### Basic Usage


To include content from another YAML file, use the **`!include`** tag. For example,

```yaml
foo: !include a.yaml
```

will be parsed as the following when reading:

```yaml
foo:
  # the whole a.yaml is included
  one: two
  three: four
  five:
    six:
      seven: eight
      nine: ten
```

> For this example to work, the file must be located in the same directory as `a.yaml`. When in another directory, you should use a relative or absolute path that can lead to the source file.

### Include Partial Content

If the source file is a mapping, you can include certain content by providing its key path.

The following example includes a certain key in [a.yaml](#usage):

```yaml
foo: !include a.yaml one
```

It will be parsed as the following when reading:

```yaml
foo: two
```

It also works if the source mapping contains multiple layers. For example,

```yaml
foo: !include a.yaml five.six.seven
```

will be parsed as the following when reading:

```yaml
foo: eight
```

Note that the key path will not be kept. 

### Mapping Merging

You can merge a mapping from another file into the current mapping using a special `<<` key:

```yaml
foo: bar
<<: !include a.yaml five.six
```

which be parsed as the following when reading:

```yaml
foo: bar
# a.yaml::five.six is merged into the current mapping
seven: eight
nine: ten
```

Note that if the source is not a mapping, an error will be raised.
