import abc
import asyncio
import warnings

from .. import utils
from ..tl import TLObject, types
from ..tl.custom.chatgetter import ChatGetter


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
            May be one or more entities (username/peer/etc.), preferably IDs.
            By default, only matching chats will be handled.

        blacklist_chats (`bool`, optional):
            Whether to treat the chats as a blacklist instead of
            as a whitelist (default). This means that every chat
            will be handled *except* those specified in ``chats``
            which will be ignored if ``blacklist_chats=True``.

        func (`callable`, optional):
            A callable (async or not) function that should accept the event as input
            parameter, and return a value indicating whether the event
            should be dispatched or not (any truthy value will do, it
            does not need to be a `bool`). It works like a custom filter:

            .. code-block:: python

                @client.on(events.NewMessage(func=lambda e: e.is_private))
                async def handler(event):
                    pass  # code here
    """
    def __init__(self, chats=None, *, blacklist_chats=False, func=None):
        self.chats = chats
        self.blacklist_chats = bool(blacklist_chats)
        self.resolved = False
        self.func = func
        self._resolve_lock = None

    @classmethod
    @abc.abstractmethod
    def build(cls, update, others=None, self_id=None):
        """
        Builds an event for the given update if possible, or returns None.

        `others` are the rest of updates that came in the same container
        as the current `update`.

        `self_id` should be the current user's ID, since it is required
        for some events which lack this information but still need it.
        """
        # TODO So many parameters specific to only some update types seems dirty

    async def resolve(self, client):
        """Helper method to allow event builders to be resolved before usage"""
        if self.resolved:
            return

        if not self._resolve_lock:
            self._resolve_lock = asyncio.Lock()

        async with self._resolve_lock:
            if not self.resolved:
                await self._resolve(client)
                self.resolved = True

    async def _resolve(self, client):
        self.chats = await _into_id_set(client, self.chats)

    def filter(self, event):
        """
        Returns a truthy value if the event passed the filter and should be
        used, or falsy otherwise. The return value may need to be awaited.

        The events must have been resolved before this can be called.
        """
        if not self.resolved:
            return

        if self.chats is not None:
            # Note: the `event.chat_id` property checks if it's `None` for us
            inside = event.chat_id in self.chats
            if inside == self.blacklist_chats:
                # If this chat matches but it's a blacklist ignore.
                # If it doesn't match but it's a whitelist ignore.
                return

        if not self.func:
            return True

        # Return the result of func directly as it may need to be awaited
        return self.func(event)


class EventCommon(ChatGetter, abc.ABC):
    """
    Intermediate class with common things to all events.

    Remember that this class implements `ChatGetter
    <telethon.tl.custom.chatgetter.ChatGetter>` which
    means you have access to all chat properties and methods.

    In addition, you can access the `original_update`
    field which contains the original :tl:`Update`.
    """
    _event_name = 'Event'

    def __init__(self, chat_peer=None, msg_id=None, broadcast=None):
        super().__init__(chat_peer, broadcast=broadcast)
        self._entities = {}
        self._client = None
        self._message_id = msg_id
        self.original_update = None

    def _set_client(self, client):
        """
        Setter so subclasses can act accordingly when the client is set.
        """
        self._client = client
        if self._chat_peer:
            self._chat, self._input_chat = utils._get_entity_pair(
                self.chat_id, self._entities, client._mb_entity_cache)
        else:
            self._chat = self._input_chat = None

    @property
    def client(self):
        """
        The `telethon.TelegramClient` that created this event.
        """
        return self._client

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
