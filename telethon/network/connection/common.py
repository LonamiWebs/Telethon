"""
This module holds the abstract `Connection` class.
"""
import abc
import asyncio
from datetime import timedelta


class Connection(abc.ABC):
    """
    Represents an abstract connection for Telegram.

    Subclasses should implement the actual protocol
    being used when encoding/decoding messages.
    """
    def __init__(self, proxy=None, timeout=timedelta(seconds=5), loop=None):
        """
        Initializes a new connection.

        :param proxy: whether to use a proxy or not.
        :param timeout: timeout to be used for all operations.
        :param loop: event loop to be used, or ``asyncio.get_event_loop()``.
        """
        self._proxy = proxy
        self._timeout = timeout
        self._loop = loop or asyncio.get_event_loop()

    @abc.abstractmethod
    def connect(self, ip, port):
        raise NotImplementedError

    @abc.abstractmethod
    def get_timeout(self):
        """Returns the timeout used by the connection."""
        raise NotImplementedError

    @abc.abstractmethod
    async def is_connected(self):
        """
        Determines whether the connection is alive or not.

        :return: true if it's connected.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def close(self):
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
