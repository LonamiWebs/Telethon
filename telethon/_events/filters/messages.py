import re
from .base import Filter


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
