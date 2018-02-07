import abc
import itertools

from .. import utils
from ..errors import RPCError
from ..extensions import markdown
from ..tl import types, functions


class _EventBuilder(abc.ABC):
    @abc.abstractmethod
    def build(self, update):
        """Builds an event for the given update if possible, or returns None"""

    @abc.abstractmethod
    def resolve(self, client):
        """Helper method to allow event builders to be resolved before usage"""


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

        chats (:obj:`entity`, optional):
            May be one or more entities (username/peer/etc.). By default,
            only matching chats will be handled.

        blacklist_chats (:obj:`bool`, optional):
            Whether to treat the the list of chats as a blacklist (if
            it matches it will NOT be handled) or a whitelist (default).
    """
    def __init__(self, incoming=None, outgoing=None,
                 chats=None, blacklist_chats=False,
                 require_input=True):
        if incoming and outgoing:
            raise ValueError('Can only set either incoming or outgoing')

        self.incoming = incoming
        self.outgoing = outgoing
        self.chats = chats
        self.blacklist_chats = blacklist_chats

    def resolve(self, client):
        if hasattr(self.chats, '__iter__') and not isinstance(self.chats, str):
            self.chats = set(utils.get_peer_id(x)
                             for x in client.get_input_entity(self.chats))
        elif self.chats is not None:
            self.chats = {utils.get_peer_id(
                          client.get_input_entity(self.chats))}

    def build(self, update):
        if isinstance(update,
                      (types.UpdateNewMessage, types.UpdateNewChannelMessage)):
            event = NewMessage.Event(update.message)
        elif isinstance(update, types.UpdateShortMessage):
            event = NewMessage.Event(types.Message(
                out=update.out,
                mentioned=update.mentioned,
                media_unread=update.media_unread,
                silent=update.silent,
                id=update.id,
                to_id=types.PeerUser(update.user_id),
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
        if all(x is None for x in (self.incoming, self.outgoing, self.chats)):
            return event

        if self.incoming and event.message.out:
            return
        if self.outgoing and not event.message.out:
            return

        if self.chats is not None:
            inside = utils.get_peer_id(event.message.to_id) in self.chats
            if inside == self.blacklist_chats:
                # If this chat matches but it's a blacklist ignore.
                # If it doesn't match but it's a whitelist ignore.
                return

        # Tests passed so return the event
        return event

    class Event:
        """
        Represents the event of a new message.

        Members:
            message (:obj:`Message`):
                This is the original ``Message`` object.

            input_chat (:obj:`InputPeer`):
                This is the input chat (private, group, megagroup or channel)
                to which the message was sent. This doesn't have the title or
                anything, but is useful if you don't need those to avoid
                further requests.

                Note that this might not be available if the library can't
                find the input chat.

            chat (:obj:`User` | :obj:`Chat` | :obj:`Channel`, optional):
                This property will make an API call the first time to get the
                most up to date version of the chat, so use with care as
                there is no caching besides local caching yet.

                ``input_chat`` needs to be available (often the case).

            is_private (:obj:`bool`):
                True if the message was sent as a private message.

            is_group (:obj:`bool`):
                True if the message was sent on a group or megagroup.

            is_channel (:obj:`bool`):
                True if the message was sent on a megagroup or channel.

            input_sender (:obj:`InputPeer`):
                This is the input version of the user who sent the message.
                Similarly to ``input_chat``, this doesn't have things like
                username or similar, but still useful in some cases.

                Note that this might not be available if the library can't
                find the input chat.

            sender (:obj:`User`):
                This property will make an API call the first time to get the
                most up to date version of the sender, so use with care as
                there is no caching besides local caching yet.

                ``input_sender`` needs to be available (often the case).

            text (:obj:`str`):
                The message text, markdown-formatted.

            raw_text (:obj:`str`):
                The raw message text, ignoring any formatting.

            is_reply (:obj:`str`):
                Whether the message is a reply to some other or not.

            reply_message (:obj:`Message`, optional):
                This property will make an API call the first time to get the
                full ``Message`` object that one was replying to, so use with
                care as there is no caching besides local caching yet.

            forward (:obj:`MessageFwdHeader`, optional):
                The unmodified ``MessageFwdHeader``, if present.

            out (:obj:`bool`):
                Whether the message is outgoing (i.e. you sent it from
                another session) or incoming (i.e. someone else sent it).
        """
        def __init__(self, message):
            self._client = None
            self.message = message
            self._text = None

            self._input_chat = None
            self._chat = None
            self._input_sender = None
            self._sender = None

            self.is_private = isinstance(message.to_id, types.PeerUser)
            self.is_group = (
                isinstance(message.to_id, (types.PeerChat, types.PeerChannel))
                and not message.post
            )
            self.is_channel = isinstance(message.to_id, types.PeerChannel)

            self.is_reply = bool(message.reply_to_msg_id)
            self._reply_message = None

        def reply(self, message, as_reply=True):
            """Replies to this message"""
            self._client.send_message(self.message.to_id, message)

        def _get_input_entity(self, msg_id, entity_id, chat=None):
            """
            Helper function to call GetMessages on the give msg_id and
            return the input entity whose ID is the given entity ID.
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
            if self._input_chat is None:
                try:
                    self._input_chat = self._client.get_input_entity(
                        self.message.to_id
                    )
                except (ValueError, TypeError):
                    # The library hasn't seen this chat, get the message
                    if not isinstance(self.message.to_id, types.PeerChannel):
                        # TODO For channels, getDifference? Maybe looking
                        # in the dialogs (which is already done) is enough.
                        self._input_chat = self._get_input_entity(
                            self.message.id,
                            utils.get_peer_id(self.message.to_id)
                        )
            return self._input_chat

        @property
        def chat(self):
            if self._chat is None and self.input_chat:
                self._chat = self._client.get_entity(self._input_chat)
            return self._chat

        @property
        def input_sender(self):
            if self._input_sender is None:
                try:
                    self._input_sender = self._client.get_input_entity(
                        self.message.from_id
                    )
                except (ValueError, TypeError):
                    if isinstance(self.message.to_id, types.PeerChannel):
                        # We can rely on self.input_chat for this
                        self._input_sender = self._get_input_entity(
                            self.message.id,
                            self.message.from_id,
                            chat=self.input_chat
                        )

            return self._client.get_input_entity(self.message.from_id)

        @property
        def sender(self):
            if self._sender is None and self.input_sender:
                self._sender = self._client.get_entity(self._input_sender)
            return self._sender

        @property
        def text(self):
            if self._text is None:
                if not self.message.entities:
                    return self.message.message
                self._text = markdown.unparse(self.message.message,
                                              self.message.entities or [])
            return self._text

        @property
        def raw_text(self):
            return self.message.message

        @property
        def reply_message(self):
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
            return self.message.fwd_from

        @property
        def out(self):
            return self.message.out
