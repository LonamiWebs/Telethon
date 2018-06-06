"""
This module holds the abstract `Connection` class.

The `Connection.send` and `Connection.recv` methods need **not** to be
safe across several tasks and may use any amount of ``await`` keywords.

The code using these `Connection`'s should be responsible for using
an ``async with asyncio.Lock:`` block when calling said methods.

Said subclasses need not to worry about reconnecting either, and
should let the errors propagate instead.
"""
import abc
from datetime import timedelta


class Connection(abc.ABC):
    """
    Represents an abstract connection for Telegram.

    Subclasses should implement the actual protocol
    being used when encoding/decoding messages.
    """
    def __init__(self, proxy=None, timeout=timedelta(seconds=5)):
        """
        Initializes a new connection.

        :param proxy: whether to use a proxy or not.
        :param timeout: timeout to be used for all operations.
        """
        self._proxy = proxy
        self._timeout = timeout

    @abc.abstractmethod
    async def connect(self, ip, port):
        raise NotImplementedError

    @abc.abstractmethod
    def get_timeout(self):
        """Returns the timeout used by the connection."""
        raise NotImplementedError

    @abc.abstractmethod
    def is_connected(self):
        """
        Determines whether the connection is alive or not.

        :return: true if it's connected.
        """
        raise NotImplementedError

    @abc.abstractmethod
    async def close(self):
        """Closes the connection."""
        raise NotImplementedError

    @abc.abstractmethod
    def clone(self):
        """Creates a copy of this Connection."""
        raise NotImplementedError

    @abc.abstractmethod
    async def recv(self):
        """Receives and unpacks a message"""
        raise NotImplementedError

    @abc.abstractmethod
    async def send(self, message):
        """Encapsulates and sends the given message"""
        raise NotImplementedError
