import re

from .common import EventBuilder, EventCommon, name_inner_event
from .. import utils
from ..extensions import markdown
from ..tl import types, functions


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
        if incoming and outgoing:
            raise ValueError('Can only set either incoming or outgoing')

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
        Represents the event of a new message.

        Members:
            message (:tl:`Message`):
                This is the original :tl:`Message` object.

            is_private (`bool`):
                True if the message was sent as a private message.

            is_group (`bool`):
                True if the message was sent on a group or megagroup.

            is_channel (`bool`):
                True if the message was sent on a megagroup or channel.

            is_reply (`str`):
                Whether the message is a reply to some other or not.
        """
        def __init__(self, message):
            if not message.out and isinstance(message.to_id, types.PeerUser):
                # Incoming message (e.g. from a bot) has to_id=us, and
                # from_id=bot (the actual "chat" from an user's perspective).
                chat_peer = types.PeerUser(message.from_id)
            else:
                chat_peer = message.to_id

            super().__init__(chat_peer=chat_peer,
                             msg_id=message.id, broadcast=bool(message.post))

            self.message = message
            self._text = None

            self._input_sender = None
            self._sender = None

            self.is_reply = bool(message.reply_to_msg_id)
            self._reply_message = None

        def respond(self, *args, **kwargs):
            """
            Responds to the message (not as a reply). Shorthand for
            `telethon.telegram_client.TelegramClient.send_message` with
            ``entity`` already set.
            """
            return self._client.send_message(self.input_chat, *args, **kwargs)

        def reply(self, *args, **kwargs):
            """
            Replies to the message (as a reply). Shorthand for
            `telethon.telegram_client.TelegramClient.send_message` with
            both ``entity`` and ``reply_to`` already set.
            """
            kwargs['reply_to'] = self.message.id
            return self._client.send_message(self.input_chat, *args, **kwargs)

        def forward_to(self, *args, **kwargs):
            """
            Forwards the message. Shorthand for
            `telethon.telegram_client.TelegramClient.forward_messages` with
            both ``messages`` and ``from_peer`` already set.
            """
            kwargs['messages'] = self.message.id
            kwargs['from_peer'] = self.input_chat
            return self._client.forward_messages(*args, **kwargs)

        def edit(self, *args, **kwargs):
            """
            Edits the message iff it's outgoing. Shorthand for
            `telethon.telegram_client.TelegramClient.edit_message` with
            both ``entity`` and ``message`` already set.

            Returns ``None`` if the message was incoming, or the edited
            :tl:`Message` otherwise.
            """
            if self.message.fwd_from:
                return None
            if not self.message.out:
                if not isinstance(self.message.to_id, types.PeerUser):
                    return None
                me = self._client.get_me(input_peer=True)
                if self.message.to_id.user_id != me.user_id:
                    return None

            return self._client.edit_message(self.input_chat,
                                             self.message,
                                             *args, **kwargs)

        def delete(self, *args, **kwargs):
            """
            Deletes the message. You're responsible for checking whether you
            have the permission to do so, or to except the error otherwise.
            Shorthand for
            `telethon.telegram_client.TelegramClient.delete_messages` with
            ``entity`` and ``message_ids`` already set.
            """
            return self._client.delete_messages(self.input_chat,
                                                [self.message],
                                                *args, **kwargs)

        @property
        def input_sender(self):
            """
            This (:tl:`InputPeer`) is the input version of the user who
            sent the message. Similarly to ``input_chat``, this doesn't have
            things like username or similar, but still useful in some cases.

            Note that this might not be available if the library can't
            find the input chat, or if the message a broadcast on a channel.
            """
            if self._input_sender is None:
                if self.is_channel and not self.is_group:
                    return None

                try:
                    self._input_sender = self._client.get_input_entity(
                        self.message.from_id
                    )
                except (ValueError, TypeError):
                    # We can rely on self.input_chat for this
                    self._sender, self._input_sender = self._get_entity(
                        self.message.id,
                        self.message.from_id,
                        chat=self.input_chat
                    )

            return self._input_sender

        @property
        def sender(self):
            """
            This (:tl:`User`) may make an API call the first time to get
            the most up to date version of the sender (mostly when the event
            doesn't belong to a channel), so keep that in mind.

            ``input_sender`` needs to be available (often the case).
            """
            if not self.input_sender:
                return None

            if self._sender is None:
                self._sender = \
                    self._entities.get(utils.get_peer_id(self._input_sender))

            if self._sender is None:
                self._sender = self._client.get_entity(self._input_sender)

            return self._sender

        @property
        def sender_id(self):
            """
            Returns the marked sender integer ID, if present.
            """
            return self.message.from_id

        @property
        def text(self):
            """
            The message text, markdown-formatted.
            """
            if self._text is None:
                if not self.message.entities:
                    return self.message.message
                self._text = markdown.unparse(self.message.message,
                                              self.message.entities or [])
            return self._text

        @property
        def raw_text(self):
            """
            The raw message text, ignoring any formatting.
            """
            return self.message.message

        @property
        def reply_message(self):
            """
            This optional :tl:`Message` will make an API call the first
            time to get the full :tl:`Message` object that one was replying to,
            so use with care as there is no caching besides local caching yet.
            """
            if not self.message.reply_to_msg_id:
                return None

            if self._reply_message is None:
                if isinstance(self.input_chat, types.InputPeerChannel):
                    r = self._client(functions.channels.GetMessagesRequest(
                        self.input_chat, [self.message.reply_to_msg_id]
                    ))
                else:
                    r = self._client(functions.messages.GetMessagesRequest(
                        [self.message.reply_to_msg_id]
                    ))
                if not isinstance(r, types.messages.MessagesNotModified):
                    self._reply_message = r.messages[0]

            return self._reply_message

        @property
        def forward(self):
            """
            The unmodified :tl:`MessageFwdHeader`, if present..
            """
            return self.message.fwd_from

        @property
        def media(self):
            """
            The unmodified :tl:`MessageMedia`, if present.
            """
            return self.message.media

        @property
        def photo(self):
            """
            If the message media is a photo,
            this returns the :tl:`Photo` object.
            """
            if isinstance(self.message.media, types.MessageMediaPhoto):
                photo = self.message.media.photo
                if isinstance(photo, types.Photo):
                    return photo

        @property
        def document(self):
            """
            If the message media is a document,
            this returns the :tl:`Document` object.
            """
            if isinstance(self.message.media, types.MessageMediaDocument):
                doc = self.message.media.document
                if isinstance(doc, types.Document):
                    return doc

        def _document_by_attribute(self, kind, condition=None):
            """
            Helper method to return the document only if it has an attribute
            that's an instance of the given kind, and passes the condition.
            """
            doc = self.document
            if doc:
                for attr in doc.attributes:
                    if isinstance(attr, kind):
                        if not condition or condition(doc):
                            return doc

        @property
        def audio(self):
            """
            If the message media is a document with an Audio attribute,
            this returns the :tl:`Document` object.
            """
            return self._document_by_attribute(types.DocumentAttributeAudio,
                                               lambda attr: not attr.voice)

        @property
        def voice(self):
            """
            If the message media is a document with a Voice attribute,
            this returns the :tl:`Document` object.
            """
            return self._document_by_attribute(types.DocumentAttributeAudio,
                                               lambda attr: attr.voice)

        @property
        def video(self):
            """
            If the message media is a document with a Video attribute,
            this returns the :tl:`Document` object.
            """
            return self._document_by_attribute(types.DocumentAttributeVideo)

        @property
        def video_note(self):
            """
            If the message media is a document with a Video attribute,
            this returns the :tl:`Document` object.
            """
            return self._document_by_attribute(types.DocumentAttributeVideo,
                                               lambda attr: attr.round_message)

        @property
        def gif(self):
            """
            If the message media is a document with an Animated attribute,
            this returns the :tl:`Document` object.
            """
            return self._document_by_attribute(types.DocumentAttributeAnimated)

        @property
        def sticker(self):
            """
            If the message media is a document with a Sticker attribute,
            this returns the :tl:`Document` object.
            """
            return self._document_by_attribute(types.DocumentAttributeSticker)

        @property
        def out(self):
            """
            Whether the message is outgoing (i.e. you sent it from
            another session) or incoming (i.e. someone else sent it).
            """
            return self.message.out
