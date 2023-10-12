from typing import Any

from .memory import MemorySession
from .storage import Storage

try:
    from .sqlite import SqliteSession
except ImportError as e:
    import_err = e

    class SqliteSession(Storage):  # type: ignore [no-redef]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise import_err from None


__all__ = ["MemorySession", "Storage", "SqliteSession"]
