import re

from .base import EventBuilder
from .._misc import utils
from .. import _tl
from ..types import _custom


class NewMessage(EventBuilder, _custom.Message):
    """
    Represents the event of a new message. This event can be treated
    to all effects as a `Message <telethon.tl.custom.message.Message>`,
    so please **refer to its documentation** to know what you can do
    with this event.

    Members:
        message (`Message <telethon.tl.custom.message.Message>`):
            This is the only difference with the received
            `Message <telethon.tl.custom.message.Message>`, and will
            return the `telethon.tl.custom.message.Message` itself,
            not the text.

            See `Message <telethon.tl.custom.message.Message>` for
            the rest of available members and methods.

        pattern_match (`obj`):
            The resulting object from calling the passed ``pattern`` function.
            Here's an example using a string (defaults to regex match):

            >>> from telethon import TelegramClient, events
            >>> client = TelegramClient(...)
            >>>
            >>> @client.on(events.NewMessage(pattern=r'hi (\\w+)!'))
            ... async def handler(event):
            ...     # In this case, the result is a ``Match`` object
            ...     # since the `str` pattern was converted into
            ...     # the ``re.compile(pattern).match`` function.
            ...     print('Welcomed', event.pattern_match.group(1))
            ...
            >>>

    Example
        .. code-block:: python

            import asyncio
            from telethon import events

            @client.on(events.NewMessage(pattern='(?i)hello.+'))
            async def handler(event):
                # Respond whenever someone says "Hello" and something else
                await event.reply('Hey!')

            @client.on(events.NewMessage(outgoing=True, pattern='!ping'))
            async def handler(event):
                # Say "!pong" whenever you send "!ping", then delete both messages
                m = await event.respond('!pong')
                await asyncio.sleep(5)
                await client.delete_messages(event.chat_id, [event.id, m.id])
    """
    @classmethod
    def _build(cls, client, update, entities):
        if isinstance(update,
                      (_tl.UpdateNewMessage, _tl.UpdateNewChannelMessage)):
            if not isinstance(update.message, _tl.Message):
                return  # We don't care about MessageService's here
            msg = update.message
        elif isinstance(update, _tl.UpdateShortMessage):
            msg = _tl.Message(
                out=update.out,
                mentioned=update.mentioned,
                media_unread=update.media_unread,
                silent=update.silent,
                id=update.id,
                peer_id=_tl.PeerUser(update.user_id),
                from_id=_tl.PeerUser(self_id if update.out else update.user_id),
                message=update.message,
                date=update.date,
                fwd_from=update.fwd_from,
                via_bot_id=update.via_bot_id,
                reply_to=update.reply_to,
                entities=update.entities,
                ttl_period=update.ttl_period
            )
        elif isinstance(update, _tl.UpdateShortChatMessage):
            msg = _tl.Message(
                out=update.out,
                mentioned=update.mentioned,
                media_unread=update.media_unread,
                silent=update.silent,
                id=update.id,
                from_id=_tl.PeerUser(self_id if update.out else update.from_id),
                peer_id=_tl.PeerChat(update.chat_id),
                message=update.message,
                date=update.date,
                fwd_from=update.fwd_from,
                via_bot_id=update.via_bot_id,
                reply_to=update.reply_to,
                entities=update.entities,
                ttl_period=update.ttl_period
            )
        else:
            return

        return cls._new(client, msg, entities, None)
