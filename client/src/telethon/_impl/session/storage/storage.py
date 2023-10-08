import abc
from typing import Optional

from ..session import Session


class Storage(abc.ABC):
    """
    Interface declaring the required methods of a :term:`session` storage.
    """

    @abc.abstractmethod
    async def load(self) -> Optional[Session]:
        """
        Load the :class:`Session` instance, if any.

        This method is called by the library prior to `connect`.

        :return: The previously-saved session.
        """

    @abc.abstractmethod
    async def save(self, session: Session) -> None:
        """
        Save the :class:`Session` instance to persistent storage.

        This method is called by the library post `disconnect`.

        :param session:
            The session information that should be persisted.
        """

    @abc.abstractmethod
    async def delete(self) -> None:
        """
        Delete the saved `Session`.

        This method is called by the library post `log_out`.

        Note that both :meth:`load` and :meth:`save` may still be called after.
        """
