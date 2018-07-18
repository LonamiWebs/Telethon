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

    async def resolve(self, client):
        pass

    @classmethod
    def build(cls, update):
        return update

    def filter(self, event):
        if not self.types or isinstance(event, self.types):
            return event
