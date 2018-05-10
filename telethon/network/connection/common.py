"""
This module holds the abstract `Connection` class.
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
    def connect(self, ip, port):
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
    def close(self):
        """Closes the connection."""
        raise NotImplementedError

    @abc.abstractmethod
    def clone(self):
        """Creates a copy of this Connection."""
        raise NotImplementedError

    @abc.abstractmethod
    def recv(self):
        """Receives and unpacks a message"""
        raise NotImplementedError

    @abc.abstractmethod
    def send(self, message):
        """Encapsulates and sends the given message"""
        raise NotImplementedError
