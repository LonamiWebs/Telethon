from .base import EventBuilder
from .._misc import utils


class Raw(EventBuilder):
    """
    Raw events are not actual events. Instead, they are the raw
    :tl:`Update` object that Telegram sends. You normally shouldn't
    need these.

    Example
        .. code-block:: python

            from telethon import events

            @client.on(events.Raw)
            async def handler(update):
                # Print all incoming updates
                print(update.stringify())
    """
    @classmethod
    def _build(cls, update, others=None, self_id=None, *todo, **todo2):
        return update
