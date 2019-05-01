import asyncio
import re

from .common import EventBuilder, EventCommon, name_inner_event, _into_id_set
from ..tl import types


@name_inner_event
class NewMessage(EventBuilder):
    """
    Represents a new message event builder.

    Args:
        incoming (`bool`, optional):
            If set to ``True``, only **incoming** messages will be handled.
            Mutually exclusive with ``outgoing`` (can only set one of either).

        outgoing (`bool`, optional):
            If set to ``True``, only **outgoing** messages will be handled.
            Mutually exclusive with ``incoming`` (can only set one of either).

        from_users (`entity`, optional):
            Unlike `chats`, this parameter filters the *senders* of the
            message. That is, only messages *sent by these users* will be
            handled. Use `chats` if you want private messages with this/these
            users. `from_users` lets you filter by messages sent by *one or
            more* users across the desired chats (doesn't need a list).

        forwards (`bool`, optional):
            Whether forwarded messages should be handled or not. By default,
            both forwarded and normal messages are included. If it's ``True``
            *only* forwards will be handled. If it's ``False`` only messages
            that are *not* forwards will be handled.

        pattern (`str`, `callable`, `Pattern`, optional):
            If set, only messages matching this pattern will be handled.
            You can specify a regex-like string which will be matched
            against the message, a callable function that returns ``True``
            if a message is acceptable, or a compiled regex pattern.
    """
    def __init__(self, chats=None, *, blacklist_chats=False, func=None,
                 incoming=None, outgoing=None,
                 from_users=None, forwards=None, pattern=None):
        if incoming and outgoing:
            incoming = outgoing = None  # Same as no filter
        elif incoming is not None and outgoing is None:
            outgoing = not incoming
        elif outgoing is not None and incoming is None:
            incoming = not outgoing
        elif all(x is not None and not x for x in (incoming, outgoing)):
            raise ValueError("Don't create an event handler if you "
                             "don't want neither incoming nor outgoing!")

        super().__init__(chats, blacklist_chats=blacklist_chats, func=func)
        self.incoming = incoming
        self.outgoing = outgoing
        self.from_users = from_users
        self.forwards = forwards
        if isinstance(pattern, str):
            self.pattern = re.compile(pattern).match
        elif not pattern or callable(pattern):
            self.pattern = pattern
        elif hasattr(pattern, 'match') and callable(pattern.match):
            self.pattern = pattern.match
        else:
            raise TypeError('Invalid pattern type given')

        # Should we short-circuit? E.g. perform no check at all
        self._no_check = all(x is None for x in (
            self.chats, self.incoming, self.outgoing, self.pattern,
            self.from_users, self.forwards, self.from_users, self.func
        ))

    async def _resolve(self, client):
        await super()._resolve(client)
        self.from_users = await _into_id_set(client, self.from_users)

    @classmethod
    def build(cls, update):
        if isinstance(update,
                      (types.UpdateNewMessage, types.UpdateNewChannelMessage)):
            if not isinstance(update.message, types.Message):
                return  # We don't care about MessageService's here
            event = cls.Event(update.message)
        elif isinstance(update, types.UpdateShortMessage):
            event = cls.Event(types.Message(
                out=update.out,
                mentioned=update.mentioned,
                media_unread=update.media_unread,
                silent=update.silent,
                id=update.id,
                # Note that to_id/from_id complement each other in private
                # messages, depending on whether the message was outgoing.
                to_id=types.PeerUser(
                    update.user_id if update.out else cls.self_id
                ),
                from_id=cls.self_id if update.out else update.user_id,
                message=update.message,
                date=update.date,
                fwd_from=update.fwd_from,
                via_bot_id=update.via_bot_id,
                reply_to_msg_id=update.reply_to_msg_id,
                entities=update.entities
            ))
        elif isinstance(update, types.UpdateShortChatMessage):
            event = cls.Event(types.Message(
                out=update.out,
                mentioned=update.mentioned,
                media_unread=update.media_unread,
                silent=update.silent,
                id=update.id,
                from_id=update.from_id,
                to_id=types.PeerChat(update.chat_id),
                message=update.message,
                date=update.date,
                fwd_from=update.fwd_from,
                via_bot_id=update.via_bot_id,
                reply_to_msg_id=update.reply_to_msg_id,
                entities=update.entities
            ))
        else:
            return

        # Make messages sent to ourselves outgoing unless they're forwarded.
        # This makes it consistent with official client's appearance.
        ori = event.message
        if isinstance(ori.to_id, types.PeerUser):
            if ori.from_id == ori.to_id.user_id and not ori.fwd_from:
                event.message.out = True

        event._entities = update._entities
        return event

    def filter(self, event):
        if self._no_check:
            return event

        if self.incoming and event.message.out:
            return
        if self.outgoing and not event.message.out:
            return
        if self.forwards is not None:
            if bool(self.forwards) != bool(event.message.fwd_from):
                return

        if self.from_users is not None:
            if event.message.from_id not in self.from_users:
                return

        if self.pattern:
            match = self.pattern(event.message.message or '')
            if not match:
                return
            event.pattern_match = match

        return super().filter(event)

    class Event(EventCommon):
        """
        Represents the event of a new message. This event can be treated
        to all effects as a `telethon.tl.custom.message.Message`, so please
        **refer to its documentation** to know what you can do with this event.

        Members:
            message (`Message <telethon.tl.custom.message.Message>`):
                This is the only difference with the received
                `telethon.tl.custom.message.Message`, and will
                return the `telethon.tl.custom.message.Message` itself,
                not the text.

                See `telethon.tl.custom.message.Message` for the rest of
                available members and methods.

            pattern_match (`obj`):
                The resulting object from calling the passed ``pattern`` function.
                Here's an example using a string (defaults to regex match):

                >>> from telethon import TelegramClient, events
                >>> client = TelegramClient(...)
                >>>
                >>> @client.on(events.NewMessage(pattern=r'hi (\\w+)!'))
                ... async def handler(event):
                ...     # In this case, the result is a ``Match`` object
                ...     # since the ``str`` pattern was converted into
                ...     # the ``re.compile(pattern).match`` function.
                ...     print('Welcomed', event.pattern_match.group(1))
                ...
                >>>
        """
        def __init__(self, message):
            self.__dict__['_init'] = False
            if not message.out and isinstance(message.to_id, types.PeerUser):
                # Incoming message (e.g. from a bot) has to_id=us, and
                # from_id=bot (the actual "chat" from a user's perspective).
                chat_peer = types.PeerUser(message.from_id)
            else:
                chat_peer = message.to_id

            super().__init__(chat_peer=chat_peer,
                             msg_id=message.id, broadcast=bool(message.post))

            self.pattern_match = None
            self.message = message

        def _set_client(self, client):
            super()._set_client(client)
            m = self.message
            m._finish_init(client, self._entities, None)
            self.__dict__['_init'] = True  # No new attributes can be set

        def __getattr__(self, item):
            if item in self.__dict__:
                return self.__dict__[item]
            else:
                return getattr(self.message, item)

        def __setattr__(self, name, value):
            if not self.__dict__['_init'] or name in self.__dict__:
                self.__dict__[name] = value
            else:
                setattr(self.message, name, value)
