import abc
import datetime
import itertools
import re

from .. import utils
from ..errors import RPCError
from ..extensions import markdown
from ..tl import types, functions


def _into_id_set(client, chats):
    """Helper util to turn the input chat or chats into a set of IDs."""
    if chats is None:
        return None

    if not utils.is_list_like(chats):
        chats = (chats,)

    result = set()
    for chat in chats:
        chat = client.get_input_entity(chat)
        if isinstance(chat, types.InputPeerSelf):
            chat = client.get_me(input_peer=True)
        result.add(utils.get_peer_id(chat))
    return result


class _EventBuilder(abc.ABC):
    """
    The common event builder, with builtin support to filter per chat.

    Args:
        chats (:obj:`entity`, optional):
            May be one or more entities (username/peer/etc.). By default,
            only matching chats will be handled.

        blacklist_chats (:obj:`bool`, optional):
            Whether to treat the the list of chats as a blacklist (if
            it matches it will NOT be handled) or a whitelist (default).
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

    def __init__(self, chat_peer=None, msg_id=None, broadcast=False):
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

    def _get_input_entity(self, msg_id, entity_id, chat=None):
        """
        Helper function to call GetMessages on the give msg_id and
        return the input entity whose ID is the given entity ID.

        If ``chat`` is present it must be an InputPeer.
        """
        try:
            if isinstance(chat, types.InputPeerChannel):
                result = self._client(
                    functions.channels.GetMessagesRequest(chat, [msg_id])
                )
            else:
                result = self._client(
                    functions.messages.GetMessagesRequest([msg_id])
                )
        except RPCError:
            return
        entity = {
            utils.get_peer_id(x): x for x in itertools.chain(
                getattr(result, 'chats', []),
                getattr(result, 'users', []))
        }.get(entity_id)
        if entity:
            return utils.get_input_peer(entity)

    @property
    def input_chat(self):
        """
        The (:obj:`InputPeer`) (group, megagroup or channel) on which
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
                        self._input_chat = self._get_input_entity(
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
        The (:obj:`User` | :obj:`Chat` | :obj:`Channel`, optional) on which
        the event occurred. This property will make an API call the first time
        to get the most up to date version of the chat, so use with care as
        there is no caching besides local caching yet.
        """
        if self._chat is None and self.input_chat:
            self._chat = self._client.get_entity(self._input_chat)
        return self._chat


class Raw(_EventBuilder):
    """
    Represents a raw event. The event is the update itself.
    """
    def resolve(self, client):
        pass

    def build(self, update):
        return update


# Classes defined here are actually Event builders
# for their inner Event classes. Inner ._client is
# set later by the creator TelegramClient.
class NewMessage(_EventBuilder):
    """
    Represents a new message event builder.

    Args:
        incoming (:obj:`bool`, optional):
            If set to ``True``, only **incoming** messages will be handled.
            Mutually exclusive with ``outgoing`` (can only set one of either).

        outgoing (:obj:`bool`, optional):
            If set to ``True``, only **outgoing** messages will be handled.
            Mutually exclusive with ``incoming`` (can only set one of either).

        pattern (:obj:`str`, :obj:`callable`, :obj:`Pattern`, optional):
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
            message (:obj:`Message`):
                This is the original ``Message`` object.

            is_private (:obj:`bool`):
                True if the message was sent as a private message.

            is_group (:obj:`bool`):
                True if the message was sent on a group or megagroup.

            is_channel (:obj:`bool`):
                True if the message was sent on a megagroup or channel.

            is_reply (:obj:`str`):
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

            self._input_chat = None
            self._chat = None
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
            This (:obj:`InputPeer`) is the input version of the user who
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
                    self._input_sender = self._get_input_entity(
                        self.message.id,
                        self.message.from_id,
                        chat=self.input_chat
                    )

            return self._input_sender

        @property
        def sender(self):
            """
            This (:obj:`User`) will make an API call the first time to get
            the most up to date version of the sender, so use with care as
            there is no caching besides local caching yet.

            ``input_sender`` needs to be available (often the case).
            """
            if self._sender is None and self.input_sender:
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
            This (:obj:`Message`, optional) will make an API call the first
            time to get the full ``Message`` object that one was replying to,
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
            The unmodified (:obj:`MessageFwdHeader`, optional).
            """
            return self.message.fwd_from

        @property
        def media(self):
            """
            The unmodified (:obj:`MessageMedia`, optional).
            """
            return self.message.media

        @property
        def photo(self):
            """
            If the message media is a photo,
            this returns the (:obj:`Photo`) object.
            """
            if isinstance(self.message.media, types.MessageMediaPhoto):
                photo = self.message.media.photo
                if isinstance(photo, types.Photo):
                    return photo

        @property
        def document(self):
            """
            If the message media is a document,
            this returns the (:obj:`Document`) object.
            """
            if isinstance(self.message.media, types.MessageMediaDocument):
                doc = self.message.media.document
                if isinstance(doc, types.Document):
                    return doc

        @property
        def out(self):
            """
            Whether the message is outgoing (i.e. you sent it from
            another session) or incoming (i.e. someone else sent it).
            """
            return self.message.out


class ChatAction(_EventBuilder):
    """
    Represents an action in a chat (such as user joined, left, or new pin).
    """
    def build(self, update):
        if isinstance(update, types.UpdateChannelPinnedMessage):
            # Telegram sends UpdateChannelPinnedMessage and then
            # UpdateNewChannelMessage with MessageActionPinMessage.
            event = ChatAction.Event(types.PeerChannel(update.channel_id),
                                     new_pin=update.id)

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
                event = ChatAction.Event(msg.to_id,
                                         added_by=True,
                                         users=msg.from_id)
            elif isinstance(action, types.MessageActionChatAddUser):
                event = ChatAction.Event(msg.to_id,
                                         added_by=msg.from_id or True,
                                         users=action.users)
            elif isinstance(action, types.MessageActionChatDeleteUser):
                event = ChatAction.Event(msg.to_id,
                                         kicked_by=msg.from_id or True,
                                         users=action.user_id)
            elif isinstance(action, types.MessageActionChatCreate):
                event = ChatAction.Event(msg.to_id,
                                         users=action.users,
                                         created=True,
                                         new_title=action.title)
            elif isinstance(action, types.MessageActionChannelCreate):
                event = ChatAction.Event(msg.to_id,
                                         created=True,
                                         users=msg.from_id,
                                         new_title=action.title)
            elif isinstance(action, types.MessageActionChatEditTitle):
                event = ChatAction.Event(msg.to_id,
                                         users=msg.from_id,
                                         new_title=action.title)
            elif isinstance(action, types.MessageActionChatEditPhoto):
                event = ChatAction.Event(msg.to_id,
                                         users=msg.from_id,
                                         new_photo=action.photo)
            elif isinstance(action, types.MessageActionChatDeletePhoto):
                event = ChatAction.Event(msg.to_id,
                                         users=msg.from_id,
                                         new_photo=True)
            else:
                return
        else:
            return

        return self._filter_event(event)

    class Event(_EventCommon):
        """
        Represents the event of a new chat action.

        Members:
            new_pin (:obj:`bool`):
                ``True`` if the pin has changed (new pin or removed).

            new_photo (:obj:`bool`):
                ``True`` if there's a new chat photo (or it was removed).

            photo (:obj:`Photo`, optional):
                The new photo (or ``None`` if it was removed).


            user_added (:obj:`bool`):
                ``True`` if the user was added by some other.

            user_joined (:obj:`bool`):
                ``True`` if the user joined on their own.

            user_left (:obj:`bool`):
                ``True`` if the user left on their own.

            user_kicked (:obj:`bool`):
                ``True`` if the user was kicked by some other.

            created (:obj:`bool`, optional):
                ``True`` if this chat was just created.

            new_title (:obj:`bool`, optional):
                The new title string for the chat, if applicable.
        """
        def __init__(self, chat_peer, new_pin=None, new_photo=None,
                     added_by=None, kicked_by=None, created=None,
                     users=None, new_title=None):
            super().__init__(chat_peer=chat_peer, msg_id=new_pin)

            self.new_pin = isinstance(new_pin, int)
            self._pinned_message = new_pin

            self.new_photo = new_photo is not None
            self.photo = \
                new_photo if isinstance(new_photo, types.Photo) else None

            self._added_by = None
            self._kicked_by = None
            self.user_added, self.user_joined, self.user_left,\
                self.user_kicked = (False, False, False, False)

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

        @property
        def pinned_message(self):
            """
            If ``new_pin`` is ``True``, this returns the (:obj:`Message`)
            object that was pinned.
            """
            if self._pinned_message == 0:
                return None

            if isinstance(self._pinned_message, int) and self.input_chat:
                r = self._client(functions.channels.GetMessagesRequest(
                    self._input_chat, [self._pinned_message]
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
                self._added_by = self._client.get_entity(self._added_by)
            return self._added_by

        @property
        def kicked_by(self):
            """
            The user who kicked ``users``, if applicable (``None`` otherwise).
            """
            if self._kicked_by and not isinstance(self._kicked_by, types.User):
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
            Input version of the self.user property.
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
            if self._users is None and self._user_peers:
                try:
                    self._users = self._client.get_entity(self._user_peers)
                except (TypeError, ValueError):
                    self._users = []

            return self._users

        @property
        def input_users(self):
            """
            Input version of the self.users property.
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

        return self._filter_event(event)

    class Event(_EventCommon):
        """
        Represents the event of an user status update (last seen, joined).

        Members:
            online (:obj:`bool`, optional):
                ``True`` if the user is currently online, ``False`` otherwise.
                Might be ``None`` if this information is not present.

            last_seen (:obj:`datetime`, optional):
                Exact date when the user was last seen if known.

            until (:obj:`datetime`, optional):
                Until when will the user remain online.

            within_months (:obj:`bool`):
                ``True`` if the user was seen within 30 days.

            within_weeks (:obj:`bool`):
                ``True`` if the user was seen within 7 days.

            recently (:obj:`bool`):
                ``True`` if the user was seen within a day.

            action (:obj:`SendMessageAction`, optional):
                The "typing" action if any the user is performing if any.

            cancel (:obj:`bool`):
                ``True`` if the action was cancelling other actions.

            typing (:obj:`bool`):
                ``True`` if the action is typing a message.

            recording (:obj:`bool`):
                ``True`` if the action is recording something.

            uploading (:obj:`bool`):
                ``True`` if the action is uploading something.

            playing (:obj:`bool`):
                ``True`` if the action is playing a game.

            audio (:obj:`bool`):
                ``True`` if what's being recorded/uploaded is an audio.

            round (:obj:`bool`):
                ``True`` if what's being recorded/uploaded is a round video.

            video (:obj:`bool`):
                ``True`` if what's being recorded/uploaded is an video.

            document (:obj:`bool`):
                ``True`` if what's being uploaded is document.

            geo (:obj:`bool`):
                ``True`` if what's being uploaded is a geo.

            photo (:obj:`bool`):
                ``True`` if what's being uploaded is a photo.

            contact (:obj:`bool`):
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

        return self._filter_event(event)


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

        return self._filter_event(event)

    class Event(_EventCommon):
        def __init__(self, deleted_ids, peer):
            super().__init__(
                types.Message((deleted_ids or [0])[0], peer, None, '')
            )
            self.deleted_id = None if not deleted_ids else deleted_ids[0]
            self.deleted_ids = self.deleted_ids


class StopPropagation(Exception):
    """
    If this Exception is found to be raised in any of the handlers for a
    given update, it will stop the execution of all other registered
    event handlers in the chain.
    Think of it like a ``StopIteration`` exception in a for loop.

    Example usage:
    ```
    @client.on(events.NewMessage)
    def delete(event):
        event.delete()
        # Other handlers won't have an event to work with
        raise StopPropagation

    @client.on(events.NewMessage)
    def _(event):
        # Will never be reached, because it is the second handler in the chain.
        pass
    ```
    """
