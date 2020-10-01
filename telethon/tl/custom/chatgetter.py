import abc

from ... import errors, utils
from ...tl import types


class ChatGetter(abc.ABC):
    """
    Helper base class that introduces the `chat`, `input_chat`
    and `chat_id` properties and `get_chat` and `get_input_chat`
    methods.
    """
    def __init__(self, chat_peer=None, *, input_chat=None, chat=None, broadcast=None):
        self._chat_peer = chat_peer
        self._input_chat = input_chat
        self._chat = chat
        self._broadcast = broadcast
        self._client = None

    @property
    def chat(self):
        """
        Returns the :tl:`User`, :tl:`Chat` or :tl:`Channel` where this object
        belongs to. It may be `None` if Telegram didn't send the chat.

        If you only need the ID, use `chat_id` instead.

        If you need to call a method which needs
        this chat, use `input_chat` instead.

        If you're using `telethon.events`, use `get_chat()` instead.
        """
        return self._chat

    async def get_chat(self):
        """
        Returns `chat`, but will make an API call to find the
        chat unless it's already cached.

        If you only need the ID, use `chat_id` instead.

        If you need to call a method which needs
        this chat, use `get_input_chat()` instead.
        """
        # See `get_sender` for information about 'min'.
        if (self._chat is None or getattr(self._chat, 'min', None))\
                and await self.get_input_chat():
            try:
                self._chat =\
                    await self._client.get_entity(self._input_chat)
            except ValueError:
                await self._refetch_chat()
        return self._chat

    @property
    def input_chat(self):
        """
        This :tl:`InputPeer` is the input version of the chat where the
        message was sent. Similarly to `input_sender
        <telethon.tl.custom.sendergetter.SenderGetter.input_sender>`, this
        doesn't have things like username or similar, but still useful in
        some cases.

        Note that this might not be available if the library doesn't
        have enough information available.
        """
        if self._input_chat is None and self._chat_peer and self._client:
            try:
                self._input_chat = self._client._entity_cache[self._chat_peer]
            except KeyError:
                pass

        return self._input_chat

    async def get_input_chat(self):
        """
        Returns `input_chat`, but will make an API call to find the
        input chat unless it's already cached.
        """
        if self.input_chat is None and self.chat_id and self._client:
            try:
                # The chat may be recent, look in dialogs
                target = self.chat_id
                async for d in self._client.iter_dialogs(100):
                    if d.id == target:
                        self._chat = d.entity
                        self._input_chat = d.input_entity
                        break
            except errors.RPCError:
                pass

        return self._input_chat

    @property
    def chat_id(self):
        """
        Returns the marked chat integer ID. Note that this value **will
        be different** from ``peer_id`` for incoming private messages, since
        the chat *to* which the messages go is to your own person, but
        the *chat* itself is with the one who sent the message.

        TL;DR; this gets the ID that you expect.

        If there is a chat in the object, `chat_id` will *always* be set,
        which is why you should use it instead of `chat.id <chat>`.
        """
        return utils.get_peer_id(self._chat_peer) if self._chat_peer else None

    @property
    def is_private(self):
        """
        `True` if the message was sent as a private message.

        Returns `None` if there isn't enough information
        (e.g. on `events.MessageDeleted <telethon.events.messagedeleted.MessageDeleted>`).
        """
        return isinstance(self._chat_peer, types.PeerUser) if self._chat_peer else None

    @property
    def is_group(self):
        """
        True if the message was sent on a group or megagroup.

        Returns `None` if there isn't enough information
        (e.g. on `events.MessageDeleted <telethon.events.messagedeleted.MessageDeleted>`).
        """
        # TODO Cache could tell us more in the future
        if self._broadcast is None and hasattr(self.chat, 'broadcast'):
            self._broadcast = bool(self.chat.broadcast)

        if isinstance(self._chat_peer, types.PeerChannel):
            if self._broadcast is None:
                return None
            else:
                return not self._broadcast

        return isinstance(self._chat_peer, types.PeerChat)

    @property
    def is_channel(self):
        """`True` if the message was sent on a megagroup or channel."""
        # The only case where chat peer could be none is in MessageDeleted,
        # however those always have the peer in channels.
        return isinstance(self._chat_peer, types.PeerChannel)

    async def _refetch_chat(self):
        """
        Re-fetches chat information through other means.
        """
