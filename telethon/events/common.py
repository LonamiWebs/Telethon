import abc
import itertools
import warnings

from .. import utils
from ..errors import RPCError
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


class EventCommon(abc.ABC):
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
        self.original_update = None

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
                    functions.channels.GetMessagesRequest(chat, [msg_id])
                )
            else:
                result = self._client(
                    functions.messages.GetMessagesRequest([msg_id])
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
