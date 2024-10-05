from typing import Any


def resolve_host_port(address: str, default_port: int = 80) -> tuple[str, int]:
    resolved = address.rsplit(':', 2)
    if len(resolved) == 2:
        return resolved[0], int(resolved[1])
    else:
        return resolved[0], default_port


def load_bytes(obj: bytes) -> Any:
    import pickle
    try:
        return pickle.loads(obj)
    except pickle.UnpicklingError:
        return obj
