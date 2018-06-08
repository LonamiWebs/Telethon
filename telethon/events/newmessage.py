import re

from .common import EventBuilder, EventCommon, name_inner_event
from ..tl import types, custom


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

        pattern (`str`, `callable`, `Pattern`, optional):
            If set, only messages matching this pattern will be handled.
            You can specify a regex-like string which will be matched
            against the message, a callable function that returns ``True``
            if a message is acceptable, or a compiled regex pattern.
    """
    def __init__(self, incoming=None, outgoing=None,
                 chats=None, blacklist_chats=False, pattern=None):
        if incoming is not None and outgoing is None:
            outgoing = not incoming
        elif outgoing is not None and incoming is None:
            incoming = not outgoing

        if incoming and outgoing:
            self.incoming = self.outgoing = None  # Same as no filter
        elif all(x is not None and not x for x in (incoming, outgoing)):
            raise ValueError("Don't create an event handler if you "
                             "don't want neither incoming or outgoing!")

        super().__init__(chats=chats, blacklist_chats=blacklist_chats)
        self.incoming = incoming
        self.outgoing = outgoing
        if isinstance(pattern, str):
            self.pattern = re.compile(pattern).match
        elif not pattern or callable(pattern):
            self.pattern = pattern
        elif hasattr(pattern, 'match') and callable(pattern.match):
            self.pattern = pattern.match
        else:
            raise TypeError('Invalid pattern type given')

    def build(self, update):
        if isinstance(update,
                      (types.UpdateNewMessage, types.UpdateNewChannelMessage)):
            if not isinstance(update.message, types.Message):
                return  # We don't care about MessageService's here
            event = NewMessage.Event(update.message)
        elif isinstance(update, types.UpdateShortMessage):
            event = NewMessage.Event(types.Message(
                out=update.out,
                mentioned=update.mentioned,
                media_unread=update.media_unread,
                silent=update.silent,
                id=update.id,
                to_id=types.PeerUser(update.user_id),
                from_id=self._self_id if update.out else update.user_id,
                message=update.message,
                date=update.date,
                fwd_from=update.fwd_from,
                via_bot_id=update.via_bot_id,
                reply_to_msg_id=update.reply_to_msg_id,
                entities=update.entities
            ))
        elif isinstance(update, types.UpdateShortChatMessage):
            event = NewMessage.Event(types.Message(
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

        event._entities = update._entities
        return self._message_filter_event(event)

    def _message_filter_event(self, event):
        # Short-circuit if we let pass all events
        if all(x is None for x in (self.incoming, self.outgoing, self.chats,
                                   self.pattern)):
            return event

        if self.incoming and event.message.out:
            return
        if self.outgoing and not event.message.out:
            return

        if self.pattern:
            match = self.pattern(event.message.message or '')
            if not match:
                return
            event.pattern_match = match

        return self._filter_event(event)

    class Event(EventCommon):
        """
        Represents the event of a new message. This event can be treated
        to all effects as a `telethon.tl.custom.message.Message`, so please
        **refer to its documentation** to know what you can do with this event.

        Members:
            message (:tl:`Message`):
                This is the only difference with the received
                `telethon.tl.custom.message.Message`, and will
                return the `telethon.tl.custom.message.Message` itself,
                not the text.

                See `telethon.tl.custom.message.Message` for the rest of
                available members and methods.
        """
        def __init__(self, message):
            self.__dict__['_init'] = False
            if not message.out and isinstance(message.to_id, types.PeerUser):
                # Incoming message (e.g. from a bot) has to_id=us, and
                # from_id=bot (the actual "chat" from an user's perspective).
                chat_peer = types.PeerUser(message.from_id)
            else:
                chat_peer = message.to_id

            super().__init__(chat_peer=chat_peer,
                             msg_id=message.id, broadcast=bool(message.post))

            self.message = message

        def _set_client(self, client):
            super()._set_client(client)
            self.message = custom.Message(
                client, self.message, self._entities, None)
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
