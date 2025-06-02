import time
from abc import ABC, abstractmethod


class ReconnectionPolicy(ABC):
    """
    Base class for reconnection policies.

    This class defines the interface for reconnection policies used by the MTSender.
    It allows for custom reconnection strategies to be implemented by subclasses.
    """

    @abstractmethod
    def should_retry(self, attempts: int) -> bool:
        """
        Determines whether the client should retry the connection attempt.
        """
        pass


class NoReconnect(ReconnectionPolicy):
    def should_retry(self, attempts: int) -> bool:
        return False


class FixedReconnect(ReconnectionPolicy):
    __slots__ = ("max_attempts", "delay")

    def __init__(self, attempts: int, delay: float):
        self.max_attempts = attempts
        self.delay = delay

    def should_retry(self, attempts: int) -> bool:
        if attempts < self.max_attempts:
            time.sleep(self.delay)
            return True

        return False
