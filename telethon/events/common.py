import abc
import warnings

from .. import utils
from ..tl import TLObject, types


async def _into_id_set(client, chats):
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
            chat = await client.get_input_entity(chat)
            if isinstance(chat, types.InputPeerSelf):
                chat = await client.get_me(input_peer=True)
            result.add(utils.get_peer_id(chat))

    return result


class EventBuilder(abc.ABC):
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

    async def resolve(self, client):
        """Helper method to allow event builders to be resolved before usage"""
        self.chats = await _into_id_set(client, self.chats)
        self._self_id = (await client.get_me(input_peer=True)).user_id

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


class EventCommon(abc.ABC):
    """
    Intermediate class with common things to all events.

    All events (except `Raw`) have ``is_private``, ``is_group``
    and ``is_channel`` boolean properties, as well as an
    ``original_update`` field containing the original :tl:`Update`.
    """
    _event_name = 'Event'

    def __init__(self, chat_peer=None, msg_id=None, broadcast=False):
        self._entities = {}
        self._client = None
        self._chat_peer = chat_peer
        self._message_id = msg_id
        self._input_chat = None
        self._chat = None
        self.original_update = None

        self.is_private = isinstance(chat_peer, types.PeerUser)
        self.is_group = (
            isinstance(chat_peer, (types.PeerChat, types.PeerChannel))
            and not broadcast
        )
        self.is_channel = isinstance(chat_peer, types.PeerChannel)

    def _set_client(self, client):
        """
        Setter so subclasses can act accordingly when the client is set.
        """
        self._client = client

    @property
    def input_chat(self):
        """
        This (:tl:`InputPeer`) is the input version of the chat where the
        event occurred. This doesn't have things like username or similar,
        but is still useful in some cases.

        Note that this might not be available if the library doesn't have
        enough information available.
        """
        if self._input_chat is None and self._chat_peer is not None:
            try:
                self._input_chat =\
                    self._client.session.get_input_entity(self._chat_peer)
            except ValueError:
                pass

        return self._input_chat

    async def get_input_chat(self):
        """
        Returns `input_chat`, but will make an API call to find the
        input chat unless it's already cached.
        """
        if self.input_chat is None and self._chat_peer is not None:
            ch = isinstance(self._chat_peer, types.PeerChannel)
            if not ch and self._message_id is not None:
                msg = await self._client.get_messages(
                    None, ids=self._message_id)
                self._chat = msg._chat
                self._input_chat = msg._input_chat
            else:
                target = utils.get_peer_id(self._chat_peer)
                async for d in self._client.iter_dialogs(100):
                    if d.id == target:
                        self._chat = d.entity
                        self._input_chat = d.input_entity
                        # TODO Don't break, exhaust the iterator, otherwise
                        # async_generator raises RuntimeError: partially-
                        # exhausted async_generator 'xyz' garbage collected
                        # break

        return self._input_chat

    @property
    def client(self):
        """
        The `telethon.TelegramClient` that created this event.
        """
        return self._client

    @property
    def chat(self):
        """
        The :tl:`User`, :tl:`Chat` or :tl:`Channel` on which
        the event occurred. This property may make an API call the first time
        to get the most up to date version of the chat (mostly when the event
        doesn't belong to a channel), so keep that in mind. You should use
        `get_chat` instead, unless you want to avoid an API call.
        """
        if not self.input_chat:
            return None

        if self._chat is None:
            self._chat = self._entities.get(utils.get_peer_id(self._chat_peer))

        return self._chat

    async def get_chat(self):
        """
        Returns `chat`, but will make an API call to find the
        chat unless it's already cached.
        """
        if self.chat is None and await self.get_input_chat():
            try:
                self._chat =\
                    await self._client.get_entity(self._input_chat)
            except ValueError:
                pass
        return self._chat

    @property
    def chat_id(self):
        """
        Returns the marked integer ID of the chat, if any.
        """
        if self._chat_peer:
            return utils.get_peer_id(self._chat_peer)

    def __str__(self):
        return TLObject.pretty_format(self.to_dict())

    def stringify(self):
        return TLObject.pretty_format(self.to_dict(), indent=0)

    def to_dict(self):
        d = {k: v for k, v in self.__dict__.items() if k[0] != '_'}
        d['_'] = self._event_name
        return d


def name_inner_event(cls):
    """Decorator to rename cls.Event 'Event' as 'cls.Event'"""
    if hasattr(cls, 'Event'):
        cls.Event._event_name = '{}.Event'.format(cls.__name__)
    else:
        warnings.warn('Class {} does not have a inner Event'.format(cls))
    return cls
