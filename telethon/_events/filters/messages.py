import re
from .base import Filter


class Incoming:
    """
    The update must be something the client received from another user,
    and not something the current user sent.
    """
    def __call__(self, event):
        return not event.out


class Outgoing:
    """
    The update must be something the current user sent,
    and not something received from another user.
    """
    def __call__(self, event):
        return event.out


class Pattern:
    """
    The update type must match the specified instances for the filter to return `True`.
    This is most useful for raw API.
    """
    def __init__(self, pattern):
        self._pattern = re.compile(pattern).match

    def __call__(self, event):
        return self._pattern(event.text)


class Data:
    """
    The update type must match the specified instances for the filter to return `True`.
    This is most useful for raw API.
    """
    def __init__(self, data):
        self._data = re.compile(data).match

    def __call__(self, event):
        return self._data(event.data)
