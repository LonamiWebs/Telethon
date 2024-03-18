import abc
from typing import Optional

from ....session import ChannelRef, GroupRef, UserRef


class Peer(abc.ABC):
    """
    The base class for all chat types.

    This will either be a :class:`User`, :class:`Group` or :class:`Channel`.
    """

    @property
    @abc.abstractmethod
    def id(self) -> int:
        """
        The peer's integer identifier.

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
        The primary *@username* of the user, group or chat.

        The returned string will *not* contain the at-sign ``@``.
        """

    @property
    @abc.abstractmethod
    def ref(self) -> UserRef | GroupRef | ChannelRef:
        """
        The reusable reference to this user, group or channel.

        This can be used to persist the reference to a database or disk,
        or to create inline mentions.

        .. seealso::

            :doc:`/concepts/peers`
        """

    @property
    def _ref(self) -> UserRef | GroupRef | ChannelRef:
        """
        Private alias that also exists in refs to make conversion trivial.
        """
        return self.ref
