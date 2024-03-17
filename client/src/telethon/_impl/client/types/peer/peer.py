import abc
from typing import Optional

from ....session import PackedChat


class Peer(abc.ABC):
    """
    The base class for all chat types.

    This will either be a :class:`User`, :class:`Group` or :class:`Channel`.
    """

    @property
    @abc.abstractmethod
    def id(self) -> int:
        """
        The chat's integer identifier.

        This identifier is always a positive number.

        This property is always present.
        """

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """
        The full name of the user, group or channel.

        For users, this will be the :attr:`User.first_name` concatenated with the :attr:`User.last_name`.

        For groups and channels, this will be their title.

        If there is no name (such as for deleted accounts), an empty string ``''`` will be returned.
        """

    @property
    @abc.abstractmethod
    def username(self) -> Optional[str]:
        """
        The primary *@username* of the chat.

        The returned string will *not* contain the at-sign ``@``.
        """

    @abc.abstractmethod
    def pack(self) -> Optional[PackedChat]:
        """
        Pack the chat into a compact and reusable object.

        This object can be easily serialized and saved to persistent storage.
        Unlike resolving usernames, packed chats can be reused without costly calls.

        .. seealso::

            :doc:`/concepts/chats`
        """
