from typing import Optional

from ..session import Session
from .storage import Storage


class MemorySession(Storage):
    """
    Session storage without persistence.

    This is the simplest storage and is the one used by default.

    Session data is only kept in memory and is not persisted to disk.
    """

    __slots__ = ("session",)

    def __init__(self, session: Optional[Session] = None):
        self.session = session

    async def load(self) -> Optional[Session]:
        return self.session

    async def save(self, session: Session) -> None:
        self.session = session

    async def delete(self) -> None:
        self.session = None
