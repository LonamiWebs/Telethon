import abc
import datetime
import itertools
import re
import warnings

from .. import utils
from ..errors import RPCError
from ..extensions import markdown
from ..tl import TLObject, types, functions


def _into_id_set(client, chats):
    """Helper util to turn the input chat or chats into a set of IDs."""
    if chats is None:
        return None

    if not utils.is_list_like(chats):
        chats = (chats,)

    result = set()
    for chat in chats:
        if isinstance(chat, int):
            if chat < 0:
                result.add(chat)  # Explicitly marked IDs are negative
            else:
                result.update({  # Support all valid types of peers
                    utils.get_peer_id(types.PeerUser(chat)),
                    utils.get_peer_id(types.PeerChat(chat)),
                    utils.get_peer_id(types.PeerChannel(chat)),
                })
        elif isinstance(chat, TLObject) and chat.SUBCLASS_OF_ID == 0x2d45687:
            # 0x2d45687 == crc32(b'Peer')
            result.add(utils.get_peer_id(chat))
        else:
            chat = client.get_input_entity(chat)
            if isinstance(chat, types.InputPeerSelf):
                chat = client.get_me(input_peer=True)
            result.add(utils.get_peer_id(chat))

    return result


class _EventBuilder(abc.ABC):
    """
    The common event builder, with builtin support to filter per chat.

    Args:
        chats (`entity`, optional):
            May be one or more entities (username/peer/etc.). By default,
            only matching chats will be handled.

        blacklist_chats (`bool`, optional):
            Whether to treat the chats as a blacklist instead of
            as a whitelist (default). This means that every chat
            will be handled *except* those specified in ``chats``
            which will be ignored if ``blacklist_chats=True``.
    """
    def __init__(self, chats=None, blacklist_chats=False):
        self.chats = chats
        self.blacklist_chats = blacklist_chats
        self._self_id = None

    @abc.abstractmethod
    def build(self, update):
        """Builds an event for the given update if possible, or returns None"""

    def resolve(self, client):
        """Helper method to allow event builders to be resolved before usage"""
        self.chats = _into_id_set(client, self.chats)
        self._self_id = client.get_me(input_peer=True).user_id

    def _filter_event(self, event):
        """
        If the ID of ``event._chat_peer`` isn't in the chats set (or it is
        but the set is a blacklist) returns ``None``, otherwise the event.
        """
        if self.chats is not None:
            inside = utils.get_peer_id(event._chat_peer) in self.chats
            if inside == self.blacklist_chats:
                # If this chat matches but it's a blacklist ignore.
                # If it doesn't match but it's a whitelist ignore.
                return None
        return event


class _EventCommon(abc.ABC):
    """Intermediate class with common things to all events"""
    _event_name = 'Event'

    def __init__(self, chat_peer=None, msg_id=None, broadcast=False):
        self._entities = {}
        self._client = None
        self._chat_peer = chat_peer
        self._message_id = msg_id
        self._input_chat = None
        self._chat = None

        self.pattern_match = None

        self.is_private = isinstance(chat_peer, types.PeerUser)
        self.is_group = (
            isinstance(chat_peer, (types.PeerChat, types.PeerChannel))
            and not broadcast
        )
        self.is_channel = isinstance(chat_peer, types.PeerChannel)

    def _get_entity(self, msg_id, entity_id, chat=None):
        """
        Helper function to call :tl:`GetMessages` on the give msg_id and
        return the input entity whose ID is the given entity ID.

        If ``chat`` is present it must be an :tl:`InputPeer`.

        Returns a tuple of ``(entity, input_peer)`` if it was found, or
        a tuple of ``(None, None)`` if it couldn't be.
        """
        try:
            if isinstance(chat, types.InputPeerChannel):
                result = self._client(
                    functions.channels.GetMessagesRequest(chat, [
                        types.InputMessageID(msg_id)
                    ])
                )
            else:
                result = self._client(
                    functions.messages.GetMessagesRequest([
                        types.InputMessageID(msg_id)
                    ])
                )
        except RPCError:
            return None, None

        entity = {
            utils.get_peer_id(x): x for x in itertools.chain(
                getattr(result, 'chats', []),
                getattr(result, 'users', []))
        }.get(entity_id)
        if entity:
            return entity, utils.get_input_peer(entity)
        else:
            return None, None

    @property
    def input_chat(self):
        """
        The (:tl:`InputPeer`) (group, megagroup or channel) on which
        the event occurred. This doesn't have the title or anything,
        but is useful if you don't need those to avoid further
        requests.

        Note that this might be ``None`` if the library can't find it.
        """

        if self._input_chat is None and self._chat_peer is not None:
            try:
                self._input_chat = self._client.get_input_entity(
                    self._chat_peer
                )
            except (ValueError, TypeError):
                # The library hasn't seen this chat, get the message
                if not isinstance(self._chat_peer, types.PeerChannel):
                    # TODO For channels, getDifference? Maybe looking
                    # in the dialogs (which is already done) is enough.
                    if self._message_id is not None:
                        self._chat, self._input_chat = self._get_entity(
                            self._message_id,
                            utils.get_peer_id(self._chat_peer)
                        )
        return self._input_chat

    @property
    def client(self):
        return self._client

    @property
    def chat(self):
        """
        The (:tl:`User` | :tl:`Chat` | :tl:`Channel`, optional) on which
        the event occurred. This property may make an API call the first time
        to get the most up to date version of the chat (mostly when the event
        doesn't belong to a channel), so keep that in mind.
        """
        if not self.input_chat:
            return None

        if self._chat is None:
            self._chat = self._entities.get(utils.get_peer_id(self._input_chat))

        if self._chat is None:
            self._chat = self._client.get_entity(self._input_chat)

        return self._chat

    def __str__(self):
        return TLObject.pretty_format(self.to_dict())

    def stringify(self):
        return TLObject.pretty_format(self.to_dict(), indent=0)

    def to_dict(self):
        d = {k: v for k, v in self.__dict__.items() if k[0] != '_'}
        d['_'] = self._event_name
        return d


class Raw(_EventBuilder):
    """
    Represents a raw event. The event is the update itself.
    """
    def resolve(self, client):
        pass

    def build(self, update):
        return update


def _name_inner_event(cls):
    """Decorator to rename cls.Event 'Event' as 'cls.Event'"""
    if hasattr(cls, 'Event'):
        cls.Event._event_name = '{}.Event'.format(cls.__name__)
    else:
        warnings.warn('Class {} does not have a inner Event'.format(cls))
    return cls


# Classes defined here are actually Event builders
# for their inner Event classes. Inner ._client is
# set later by the creator TelegramClient.
@_name_inner_event
class NewMessage(_EventBuilder):
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

    class Event(_EventCommon):
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
            Responds to the message (not as a reply). This is a shorthand for
            ``client.send_message(event.chat, ...)``.
            """
            return self._client.send_message(self.input_chat, *args, **kwargs)

        def reply(self, *args, **kwargs):
            """
            Replies to the message (as a reply). This is a shorthand for
            ``client.send_message(event.chat, ..., reply_to=event.message.id)``.
            """
            kwargs['reply_to'] = self.message.id
            return self._client.send_message(self.input_chat, *args, **kwargs)

        def forward_to(self, *args, **kwargs):
            """
            Forwards the message. This is a shorthand for
            ``client.forward_messages(entity, event.message, event.chat)``.
            """
            kwargs['messages'] = [self.message.id]
            kwargs['from_peer'] = self.input_chat
            return self._client.forward_messages(*args, **kwargs)

        def edit(self, *args, **kwargs):
            """
            Edits the message iff it's outgoing. This is a shorthand for
            ``client.edit_message(event.chat, event.message, ...)``.

            Returns ``None`` if the message was incoming,
            or the edited message otherwise.
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
            This is a shorthand for
            ``client.delete_messages(event.chat, event.message, ...)``.
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
                        self.input_chat, [
                            types.InputMessageID(self.message.reply_to_msg_id)
                        ]
                    ))
                else:
                    r = self._client(functions.messages.GetMessagesRequest(
                        [types.InputMessageID(self.message.reply_to_msg_id)]
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


@_name_inner_event
class ChatAction(_EventBuilder):
    """
    Represents an action in a chat (such as user joined, left, or new pin).
    """
    def build(self, update):
        if isinstance(update, types.UpdateChannelPinnedMessage) and update.id == 0:
            # Telegram does not always send
            # UpdateChannelPinnedMessage for new pins
            # but always for unpin, with update.id = 0
            event = ChatAction.Event(types.PeerChannel(update.channel_id),
                                     unpin=True)

        elif isinstance(update, types.UpdateChatParticipantAdd):
            event = ChatAction.Event(types.PeerChat(update.chat_id),
                                     added_by=update.inviter_id or True,
                                     users=update.user_id)

        elif isinstance(update, types.UpdateChatParticipantDelete):
            event = ChatAction.Event(types.PeerChat(update.chat_id),
                                     kicked_by=True,
                                     users=update.user_id)

        elif (isinstance(update, (
                types.UpdateNewMessage, types.UpdateNewChannelMessage))
              and isinstance(update.message, types.MessageService)):
            msg = update.message
            action = update.message.action
            if isinstance(action, types.MessageActionChatJoinedByLink):
                event = ChatAction.Event(msg,
                                         added_by=True,
                                         users=msg.from_id)
            elif isinstance(action, types.MessageActionChatAddUser):
                event = ChatAction.Event(msg,
                                         added_by=msg.from_id or True,
                                         users=action.users)
            elif isinstance(action, types.MessageActionChatDeleteUser):
                event = ChatAction.Event(msg,
                                         kicked_by=msg.from_id or True,
                                         users=action.user_id)
            elif isinstance(action, types.MessageActionChatCreate):
                event = ChatAction.Event(msg,
                                         users=action.users,
                                         created=True,
                                         new_title=action.title)
            elif isinstance(action, types.MessageActionChannelCreate):
                event = ChatAction.Event(msg,
                                         created=True,
                                         users=msg.from_id,
                                         new_title=action.title)
            elif isinstance(action, types.MessageActionChatEditTitle):
                event = ChatAction.Event(msg,
                                         users=msg.from_id,
                                         new_title=action.title)
            elif isinstance(action, types.MessageActionChatEditPhoto):
                event = ChatAction.Event(msg,
                                         users=msg.from_id,
                                         new_photo=action.photo)
            elif isinstance(action, types.MessageActionChatDeletePhoto):
                event = ChatAction.Event(msg,
                                         users=msg.from_id,
                                         new_photo=True)
            elif isinstance(action, types.MessageActionPinMessage):
                # Telegram always sends this service message for new pins
                event = ChatAction.Event(msg,
                                         users=msg.from_id,
                                         new_pin=msg.reply_to_msg_id)
            else:
                return
        else:
            return

        event._entities = update._entities
        return self._filter_event(event)

    class Event(_EventCommon):
        """
        Represents the event of a new chat action.

        Members:
            new_pin (`bool`):
                ``True`` if there is a new pin.

            new_photo (`bool`):
                ``True`` if there's a new chat photo (or it was removed).

            photo (:tl:`Photo`, optional):
                The new photo (or ``None`` if it was removed).


            user_added (`bool`):
                ``True`` if the user was added by some other.

            user_joined (`bool`):
                ``True`` if the user joined on their own.

            user_left (`bool`):
                ``True`` if the user left on their own.

            user_kicked (`bool`):
                ``True`` if the user was kicked by some other.

            created (`bool`, optional):
                ``True`` if this chat was just created.

            new_title (`bool`, optional):
                The new title string for the chat, if applicable.

            unpin (`bool`):
                ``True`` if the existing pin gets unpinned.
        """
        def __init__(self, where, new_pin=None, new_photo=None,
                     added_by=None, kicked_by=None, created=None,
                     users=None, new_title=None, unpin=None):
            if isinstance(where, types.MessageService):
                self.action_message = where
                where = where.to_id
            else:
                self.action_message = None

            super().__init__(chat_peer=where, msg_id=new_pin)

            self.new_pin = isinstance(new_pin, int)
            self._pinned_message = new_pin

            self.new_photo = new_photo is not None
            self.photo = \
                new_photo if isinstance(new_photo, types.Photo) else None

            self._added_by = None
            self._kicked_by = None
            self.user_added, self.user_joined, self.user_left,\
                self.user_kicked, self.unpin = (False, False, False, False, False)

            if added_by is True:
                self.user_joined = True
            elif added_by:
                self.user_added = True
                self._added_by = added_by

            if kicked_by is True:
                self.user_left = True
            elif kicked_by:
                self.user_kicked = True
                self._kicked_by = kicked_by

            self.created = bool(created)
            self._user_peers = users if isinstance(users, list) else [users]
            self._users = None
            self._input_users = None
            self.new_title = new_title
            self.unpin = unpin

        def respond(self, *args, **kwargs):
            """
            Responds to the chat action message (not as a reply).
            Shorthand for ``client.send_message(event.chat, ...)``.
            """
            return self._client.send_message(self.input_chat, *args, **kwargs)

        def reply(self, *args, **kwargs):
            """
            Replies to the chat action message (as a reply). Shorthand for
            ``client.send_message(event.chat, ..., reply_to=event.message.id)``.

            Has the same effect as ``.respond()`` if there is no message.
            """
            if not self.action_message:
                return self.respond(*args, **kwargs)

            kwargs['reply_to'] = self.action_message.id
            return self._client.send_message(self.input_chat, *args, **kwargs)

        def delete(self, *args, **kwargs):
            """
            Deletes the chat action message. You're responsible for checking
            whether you have the permission to do so, or to except the error
            otherwise. This is a shorthand for
            ``client.delete_messages(event.chat, event.message, ...)``.

            Does nothing if no message action triggered this event.
            """
            if self.action_message:
                return self._client.delete_messages(self.input_chat,
                                                    [self.action_message],
                                                    *args, **kwargs)

        @property
        def pinned_message(self):
            """
            If ``new_pin`` is ``True``, this returns the (:tl:`Message`)
            object that was pinned.
            """
            if self._pinned_message == 0:
                return None

            if isinstance(self._pinned_message, int) and self.input_chat:
                r = self._client(functions.channels.GetMessagesRequest(
                    self._input_chat, [
                        types.InputMessageID(self._pinned_message)
                    ]
                ))
                try:
                    self._pinned_message = next(
                        x for x in r.messages
                        if isinstance(x, types.Message)
                        and x.id == self._pinned_message
                    )
                except StopIteration:
                    pass

            if isinstance(self._pinned_message, types.Message):
                return self._pinned_message

        @property
        def added_by(self):
            """
            The user who added ``users``, if applicable (``None`` otherwise).
            """
            if self._added_by and not isinstance(self._added_by, types.User):
                self._added_by =\
                    self._entities.get(utils.get_peer_id(self._added_by))

                if not self._added_by:
                    self._added_by = self._client.get_entity(self._added_by)

            return self._added_by

        @property
        def kicked_by(self):
            """
            The user who kicked ``users``, if applicable (``None`` otherwise).
            """
            if self._kicked_by and not isinstance(self._kicked_by, types.User):
                self._kicked_by =\
                    self._entities.get(utils.get_peer_id(self._kicked_by))

                if not self._kicked_by:
                    self._kicked_by = self._client.get_entity(self._kicked_by)

            return self._kicked_by

        @property
        def user(self):
            """
            The single user that takes part in this action (e.g. joined).

            Might be ``None`` if the information can't be retrieved or
            there is no user taking part.
            """
            if self.users:
                return self._users[0]

        @property
        def input_user(self):
            """
            Input version of the ``self.user`` property.
            """
            if self.input_users:
                return self._input_users[0]

        @property
        def users(self):
            """
            A list of users that take part in this action (e.g. joined).

            Might be empty if the information can't be retrieved or there
            are no users taking part.
            """
            if not self._user_peers:
                return []

            if self._users is None:
                have, missing = [], []
                for peer in self._user_peers:
                    user = self._entities.get(utils.get_peer_id(peer))
                    if user:
                        have.append(user)
                    else:
                        missing.append(peer)

                try:
                    missing = self._client.get_entity(missing)
                except (TypeError, ValueError):
                    missing = []

                self._users = have + missing

            return self._users

        @property
        def input_users(self):
            """
            Input version of the ``self.users`` property.
            """
            if self._input_users is None and self._user_peers:
                self._input_users = []
                for peer in self._user_peers:
                    try:
                        self._input_users.append(self._client.get_input_entity(
                            peer
                        ))
                    except (TypeError, ValueError):
                        pass
            return self._input_users


@_name_inner_event
class UserUpdate(_EventBuilder):
    """
    Represents an user update (gone online, offline, joined Telegram).
    """
    def build(self, update):
        if isinstance(update, types.UpdateUserStatus):
            event = UserUpdate.Event(update.user_id,
                                     status=update.status)
        else:
            return

        event._entities = update._entities
        return self._filter_event(event)

    class Event(_EventCommon):
        """
        Represents the event of an user status update (last seen, joined).

        Members:
            online (`bool`, optional):
                ``True`` if the user is currently online, ``False`` otherwise.
                Might be ``None`` if this information is not present.

            last_seen (`datetime`, optional):
                Exact date when the user was last seen if known.

            until (`datetime`, optional):
                Until when will the user remain online.

            within_months (`bool`):
                ``True`` if the user was seen within 30 days.

            within_weeks (`bool`):
                ``True`` if the user was seen within 7 days.

            recently (`bool`):
                ``True`` if the user was seen within a day.

            action (:tl:`SendMessageAction`, optional):
                The "typing" action if any the user is performing if any.

            cancel (`bool`):
                ``True`` if the action was cancelling other actions.

            typing (`bool`):
                ``True`` if the action is typing a message.

            recording (`bool`):
                ``True`` if the action is recording something.

            uploading (`bool`):
                ``True`` if the action is uploading something.

            playing (`bool`):
                ``True`` if the action is playing a game.

            audio (`bool`):
                ``True`` if what's being recorded/uploaded is an audio.

            round (`bool`):
                ``True`` if what's being recorded/uploaded is a round video.

            video (`bool`):
                ``True`` if what's being recorded/uploaded is an video.

            document (`bool`):
                ``True`` if what's being uploaded is document.

            geo (`bool`):
                ``True`` if what's being uploaded is a geo.

            photo (`bool`):
                ``True`` if what's being uploaded is a photo.

            contact (`bool`):
                ``True`` if what's being uploaded (selected) is a contact.
        """
        def __init__(self, user_id, status=None, typing=None):
            super().__init__(types.PeerUser(user_id))

            self.online = None if status is None else \
                isinstance(status, types.UserStatusOnline)

            self.last_seen = status.was_online if \
                isinstance(status, types.UserStatusOffline) else None

            self.until = status.expires if \
                isinstance(status, types.UserStatusOnline) else None

            if self.last_seen:
                diff = datetime.datetime.now() - self.last_seen
                if diff < datetime.timedelta(days=30):
                    self.within_months = True
                    if diff < datetime.timedelta(days=7):
                        self.within_weeks = True
                        if diff < datetime.timedelta(days=1):
                            self.recently = True
            else:
                self.within_months = self.within_weeks = self.recently = False
                if isinstance(status, (types.UserStatusOnline,
                                       types.UserStatusRecently)):
                    self.within_months = self.within_weeks = True
                    self.recently = True
                elif isinstance(status, types.UserStatusLastWeek):
                    self.within_months = self.within_weeks = True
                elif isinstance(status, types.UserStatusLastMonth):
                    self.within_months = True

            self.action = typing
            if typing:
                self.cancel = self.typing = self.recording = self.uploading = \
                    self.playing = False
                self.audio = self.round = self.video = self.document = \
                    self.geo = self.photo = self.contact = False

                if isinstance(typing, types.SendMessageCancelAction):
                    self.cancel = True
                elif isinstance(typing, types.SendMessageTypingAction):
                    self.typing = True
                elif isinstance(typing, types.SendMessageGamePlayAction):
                    self.playing = True
                elif isinstance(typing, types.SendMessageGeoLocationAction):
                    self.geo = True
                elif isinstance(typing, types.SendMessageRecordAudioAction):
                    self.recording = self.audio = True
                elif isinstance(typing, types.SendMessageRecordRoundAction):
                    self.recording = self.round = True
                elif isinstance(typing, types.SendMessageRecordVideoAction):
                    self.recording = self.video = True
                elif isinstance(typing, types.SendMessageChooseContactAction):
                    self.uploading = self.contact = True
                elif isinstance(typing, types.SendMessageUploadAudioAction):
                    self.uploading = self.audio = True
                elif isinstance(typing, types.SendMessageUploadDocumentAction):
                    self.uploading = self.document = True
                elif isinstance(typing, types.SendMessageUploadPhotoAction):
                    self.uploading = self.photo = True
                elif isinstance(typing, types.SendMessageUploadRoundAction):
                    self.uploading = self.round = True
                elif isinstance(typing, types.SendMessageUploadVideoAction):
                    self.uploading = self.video = True

        @property
        def user(self):
            """Alias around the chat (conversation)."""
            return self.chat


@_name_inner_event
class MessageEdited(NewMessage):
    """
    Event fired when a message has been edited.
    """
    def build(self, update):
        if isinstance(update, (types.UpdateEditMessage,
                               types.UpdateEditChannelMessage)):
            event = MessageEdited.Event(update.message)
        else:
            return

        event._entities = update._entities
        return self._message_filter_event(event)

    class Event(NewMessage.Event):
        pass  # Required if we want a different name for it


@_name_inner_event
class MessageDeleted(_EventBuilder):
    """
    Event fired when one or more messages are deleted.
    """
    def build(self, update):
        if isinstance(update, types.UpdateDeleteMessages):
            event = MessageDeleted.Event(
                deleted_ids=update.messages,
                peer=None
            )
        elif isinstance(update, types.UpdateDeleteChannelMessages):
            event = MessageDeleted.Event(
                deleted_ids=update.messages,
                peer=types.PeerChannel(update.channel_id)
            )
        else:
            return

        event._entities = update._entities
        return self._filter_event(event)

    class Event(_EventCommon):
        def __init__(self, deleted_ids, peer):
            super().__init__(
                chat_peer=peer, msg_id=(deleted_ids or [0])[0]
            )
            self.deleted_id = None if not deleted_ids else deleted_ids[0]
            self.deleted_ids = deleted_ids


@_name_inner_event
class MessageRead(_EventBuilder):
    """
    Event fired when one or more messages have been read.

    Args:
        inbox (`bool`, optional):
            If this argument is ``True``, then when you read someone else's
            messages the event will be fired. By default (``False``) only
            when messages you sent are read by someone else will fire it.
    """
    def __init__(self, inbox=False, chats=None, blacklist_chats=None):
        super().__init__(chats, blacklist_chats)
        self.inbox = inbox

    def build(self, update):
        if isinstance(update, types.UpdateReadHistoryInbox):
            event = MessageRead.Event(update.peer, update.max_id, False)
        elif isinstance(update, types.UpdateReadHistoryOutbox):
            event = MessageRead.Event(update.peer, update.max_id, True)
        elif isinstance(update, types.UpdateReadChannelInbox):
            event = MessageRead.Event(types.PeerChannel(update.channel_id),
                                      update.max_id, False)
        elif isinstance(update, types.UpdateReadChannelOutbox):
            event = MessageRead.Event(types.PeerChannel(update.channel_id),
                                      update.max_id, True)
        elif isinstance(update, types.UpdateReadMessagesContents):
            event = MessageRead.Event(message_ids=update.messages,
                                      contents=True)
        elif isinstance(update, types.UpdateChannelReadMessagesContents):
            event = MessageRead.Event(types.PeerChannel(update.channel_id),
                                      message_ids=update.messages,
                                      contents=True)
        else:
            return

        if self.inbox == event.outbox:
            return

        event._entities = update._entities
        return self._filter_event(event)

    class Event(_EventCommon):
        """
        Represents the event of one or more messages being read.

        Members:
            max_id (`int`):
                Up to which message ID has been read. Every message
                with an ID equal or lower to it have been read.

            outbox (`bool`):
                ``True`` if someone else has read your messages.

            contents (`bool`):
                ``True`` if what was read were the contents of a message.
                This will be the case when e.g. you play a voice note.
                It may only be set on ``inbox`` events.
        """
        def __init__(self, peer=None, max_id=None, out=False, contents=False,
                     message_ids=None):
            self.outbox = out
            self.contents = contents
            self._message_ids = message_ids or []
            self._messages = None
            self.max_id = max_id or max(message_ids or [], default=None)
            super().__init__(peer, self.max_id)

        @property
        def inbox(self):
            """
            ``True`` if you have read someone else's messages.
            """
            return not self.outbox

        @property
        def message_ids(self):
            """
            The IDs of the messages **which contents'** were read.

            Use :meth:`is_read` if you need to check whether a message
            was read instead checking if it's in here.
            """
            return self._message_ids

        @property
        def messages(self):
            """
            The list of :tl:`Message` **which contents'** were read.

            Use :meth:`is_read` if you need to check whether a message
            was read instead checking if it's in here.
            """
            if self._messages is None:
                chat = self.input_chat
                if not chat:
                    self._messages = []
                elif isinstance(chat, types.InputPeerChannel):
                    ids = [types.InputMessageID(x) for x in self._message_ids]
                    self._messages =\
                        self._client(functions.channels.GetMessagesRequest(
                            chat, ids
                        )).messages
                else:
                    ids = [types.InputMessageID(x) for x in self._message_ids]
                    self._messages =\
                        self._client(functions.messages.GetMessagesRequest(
                            ids
                        )).messages

            return self._messages

        def is_read(self, message):
            """
            Returns ``True`` if the given message (or its ID) has been read.

            If a list-like argument is provided, this method will return a
            list of booleans indicating which messages have been read.
            """
            if utils.is_list_like(message):
                return [(m if isinstance(m, int) else m.id) <= self.max_id
                        for m in message]
            else:
                return (message if isinstance(message, int)
                        else message.id) <= self.max_id

        def __contains__(self, message):
            """``True`` if the message(s) are read message."""
            if utils.is_list_like(message):
                return all(self.is_read(message))
            else:
                return self.is_read(message)


class StopPropagation(Exception):
    """
    If this exception is raised in any of the handlers for a given event,
    it will stop the execution of all other registered event handlers.
    It can be seen as the ``StopIteration`` in a for loop but for events.

    Example usage:
        >>> @client.on(events.NewMessage)
        ... def delete(event):
        ...     event.delete()
        ...     # No other event handler will have a chance to handle this event
        ...     raise StopPropagation
        ...
        >>> @client.on(events.NewMessage)
        ... def _(event):
        ...     # Will never be reached, because it is the second handler
        ...     pass
    """
    # For some reason Sphinx wants the silly >>> or
    # it will show warnings and look bad when generated.
    pass
