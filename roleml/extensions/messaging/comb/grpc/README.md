# Recompile the Protobuf

To recompile the protobuf file (`protos/messaging.proto`), install `grpcio-tools`, and run the following command in this directory:

```shell
python -m grpc_tools.protoc -I./protos --python_out=. --pyi_out=. --grpc_python_out=. ./protos/messaging.proto
```

After recompiling, make sure to change the import statement in `messaging_pb2_grpc.py` to relative import:

```python
# BEFORE
import messaging_pb2 as messaging__pb2
# AFTER
from ..grpc import messaging_pb2 as messaging__pb2
```
