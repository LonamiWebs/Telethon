import abc
from typing import Optional

from ..session import Session


class Storage(abc.ABC):
    @abc.abstractmethod
    async def load(self) -> Optional[Session]:
        """
        Load the `Session` instance, if any.

        This method is called by the library prior to `connect`.
        """

    @abc.abstractmethod
    async def save(self, session: Session) -> None:
        """
        Save the `Session` instance to persistent storage.

        This method is called by the library post `disconnect`.
        """

    @abc.abstractmethod
    async def delete(self) -> None:
        """
        Delete the saved `Session`.

        This method is called by the library post `log_out`.
        """
