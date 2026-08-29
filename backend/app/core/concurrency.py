from collections.abc import Callable
from functools import wraps
from typing import Any, Protocol, cast


class Lock(Protocol):
    def __enter__(self) -> object: ...

    def __exit__(self, *args: object) -> None: ...


class LockOwner(Protocol):
    _lock: Lock


def synchronized[Method: Callable[..., Any]](method: Method) -> Method:
    @wraps(method)
    def wrapper(self: LockOwner, *args: Any, **kwargs: Any) -> Any:
        with self._lock:
            return method(self, *args, **kwargs)

    return cast(Method, wrapper)
