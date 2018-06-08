from .common import EventBuilder
from .. import utils


class Raw(EventBuilder):
    """
    Represents a raw event. The event is the update itself.

    Args:
        types (`list` | `tuple` | `type`, optional):
            The type or types that the :tl:`Update` instance must be.
            Equivalent to ``if not isinstance(update, types): return``.
    """
    def __init__(self, types=None):
        super().__init__()
        if not types:
            self.types = None
        elif not utils.is_list_like(types):
            assert isinstance(types, type)
            self.types = types
        else:
            assert all(isinstance(x, type) for x in types)
            self.types = tuple(types)

    def resolve(self, client):
        pass

    def build(self, update):
        if not self.types or isinstance(update, self.types):
            return update
