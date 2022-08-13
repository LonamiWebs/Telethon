from .base import Filter


class Types:
    """
    The update type must match the specified instances for the filter to return `True`.
    This is most useful for raw API.
    """
    def __init__(self, types):
        self._types = types

    def __call__(self, event):
        return isinstance(event, self._types)
