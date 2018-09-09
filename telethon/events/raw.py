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
    def __init__(self, types=None, *, func=None):
        super().__init__(func=func)
        if not types:
            self.types = None
        elif not utils.is_list_like(types):
            if not isinstance(types, type):
                raise TypeError('Invalid input type given %s', types)

            self.types = types
        else:
            if not all(isinstance(x, type) for x in types):
                raise TypeError('Invalid input types given %s', types)

            self.types = tuple(types)

    async def resolve(self, client):
        self.resolved = True

    @classmethod
    def build(cls, update):
        return update

    def filter(self, event):
        if ((not self.types or isinstance(event, self.types))
                and (not self.func or self.func(event))):
            return event
