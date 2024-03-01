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

        This method is called by the library prior to ``connect``.

        :return: The previously-saved session.
        """

    @abc.abstractmethod
    async def save(self, session: Session) -> None:
        """
        Save the :class:`Session` instance to persistent storage.

        This method is called by the library after significant changes to the session,
        such as login, logout, or to persist the update state prior to disconnection.

        :param session:
            The session information that should be persisted.
        """

    @abc.abstractmethod
    async def close(self) -> None:
        """
        Close the :class:`Session` instance, if it was still open.

        This method is called by the library post ``disconnect``,
        even if the call to :meth:`save` failed.

        Note that :meth:`load` may still be called after,
        in which case the session should be reopened.
        """
