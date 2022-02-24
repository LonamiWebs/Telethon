from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
from dataclasses import dataclass
import mimetypes
from .chatgetter import ChatGetter
from .sendergetter import SenderGetter
from .messagebutton import MessageButton
from .forward import Forward
from .file import File
from .inputfile import InputFile
from .inputmessage import InputMessage
from .button import build_reply_markup
from ..._misc import utils, helpers, tlobject, markdown, html
from ... import _tl, _misc


if TYPE_CHECKING:
    from ..._misc import hints


def _fwd(field, doc):
    def fget(self):
        return getattr(self._chat, field, None)

    def fset(self, value):
        object.__setattr__(self._chat, field, value)

    return property(fget, fset, None, doc)


@dataclass(frozen=True)
class _TinyChat:
    __slots__ = ('id', 'access_hash')

    id: int
    access_hash: int


@dataclass(frozen=True)
class _TinyChannel:
    __slots__ = ('id', 'access_hash', 'megagroup')

    id: int
    access_hash: int
    megagroup: bool  # gigagroup is not present in channelForbidden but megagroup is


class Chat:
    """
    Represents a :tl:`Chat` or :tl:`Channel` (or their empty and forbidden variants) from the API.
    """

    id = _fwd('id', """
        The chat identifier. This is the only property which will **always** be present.
    """)

    title = _fwd('title', """
        The chat title. It will be `None` for empty chats.
    """)

    username = _fwd('username', """
        The public `username` of the chat.
    """)

    participants_count = _fwd('participants_count', """
        The number of participants who are currently joined to the chat.
        It will be `None` for forbidden and empty chats or if the information isn't known.
    """)

    broadcast = _fwd('broadcast', """
        `True` if the chat is a broadcast channel.
    """)

    megagroup = _fwd('megagroup', """
        `True` if the chat is a supergroup.
    """)

    gigagroup = _fwd('gigagroup', """
        `True` if the chat used to be a `megagroup` but is now a broadcast group.
    """)

    verified = _fwd('verified', """
        `True` if the chat has been verified as official by Telegram.
    """)

    scam = _fwd('scam', """
        `True` if the chat has been flagged as scam.
    """)

    fake = _fwd('fake', """
        `True` if the chat has been flagged as fake.
    """)

    creator = _fwd('creator', """
        `True` if the logged-in account is the creator of the chat.
    """)

    kicked = _fwd('kicked', """
        `True` if the logged-in account was kicked from the chat.
    """)

    left = _fwd('left', """
        `True` if the logged-in account has left the chat.
    """)

    restricted = _fwd('restricted', """
        `True` if the logged-in account cannot write in the chat.
    """)

    slowmode_enabled = _fwd('slowmode_enabled', """
        `True` if the chat currently has slowmode enabled.
    """)

    signatures = _fwd('signatures', """
        `True` if signatures are enabled in a broadcast channel.
    """)

    admin_rights = _fwd('admin_rights', """
        Administrator rights the logged-in account has in the chat.
    """)

    banned_rights = _fwd('banned_rights', """
        Banned rights the logged-in account has in the chat.
    """)

    default_banned_rights = _fwd('default_banned_rights', """
        The default banned rights for every non-admin user in the chat.
    """)

    @property
    def forbidden(self):
        """
        `True` if access to this channel is forbidden.
        """
        return isinstance(self._chat, (_tl.ChatForbidden, _tl.ChannelForbidden))

    @property
    def forbidden_until(self):
        """
        If access to the chat is only temporarily `forbidden`, returns when access will be regained.
        """
        try:
            return self._chat.until_date
        except AttributeError:
            return None

    @property
    def restriction_reasons(self):
        """
        Returns a possibly-empty list of reasons why the chat is restricted to some platforms.
        """
        try:
            return self._chat.restriction_reason or []
        except AttributeError:
            return []

    @property
    def migrated_to(self):
        """
        If the current chat has migrated to a larger group, returns the new `Chat`.
        """
        try:
            migrated = self._chat.migrated_to
        except AttributeError:
            migrated = None

        if migrated is None:
            return migrated

        # Small chats don't migrate to other small chats, nor do they migrate to broadcast channels
        return type(self)._new(self._client, _TinyChannel(migrated.channel_id, migrated.access_hash, True))

    def __init__(self):
        raise TypeError('You cannot create Chat instances by hand!')

    @classmethod
    def _new(cls, client, chat):
        self = cls.__new__(cls)
        self._client = client

        self._chat = chat
        if isinstance(cls, Entity):
            if chat.is_user:
                raise TypeError('Tried to construct Chat with non-chat Entity')
            elif chat.ty == EntityType.GROUP:
                self._chat = _TinyChat(chat.id)
            else:
                self._chat = _TinyChannel(chat.id, chat.hash, chat.is_group)
        else:
            self._chat = chat

        self._full = None
        return self

    async def fetch(self, *, full=False):
        """
        Perform an API call to fetch fresh information about this chat.

        Returns itself, but with the information fetched (allowing you to chain the call).

        If ``full`` is ``True``, the full information about the user will be fetched,
        which will include things like ``about``.
        """
        return self

    def compact(self):
        """
        Return a compact representation of this user, useful for storing for later use.
        """
        raise RuntimeError('TODO')

    @property
    def client(self):
        """
        Returns the `TelegramClient <telethon.client.telegramclient.TelegramClient>`
        which returned this user from a friendly method.
        """
        return self._client

    def to_dict(self):
        return self._user.to_dict()

    def __repr__(self):
        return helpers.pretty_print(self)

    def __str__(self):
        return helpers.pretty_print(self, max_depth=2)

    def stringify(self):
        return helpers.pretty_print(self, indent=0)

    @property
    def is_user(self):
        """
        Returns `False`.

        This property also exists in `User`, where it returns `True`.

        .. code-block:: python

            if message.chat.is_user:
                ...  # do stuff
        """
        return False

    @property
    def is_group(self):
        """
        Returns `True` if the chat is a small group chat or `megagroup`_.

        This property also exists in `User`, where it returns `False`.

        .. code-block:: python

            if message.chat.is_group:
                ...  # do stuff

        .. _megagroup: https://telegram.org/blog/supergroups5k
        """
        return isinstance(self._chat, (_tl.Chat, _TinyChat, _tl.ChatForbidden, _tl.ChatEmpty)) or self._chat.megagroup

    @property
    def is_broadcast(self):
        """
        Returns `True` if the chat is a broadcast channel group chat or `broadcast group`_.

        This property also exists in `User`, where it returns `False`.

        .. code-block:: python

            if message.chat.is_broadcast:
                ...  # do stuff

        .. _broadcast group: https://telegram.org/blog/autodelete-inv2#groups-with-unlimited-members
        """
        return not self.is_group

    @property
    def full_name(self):
        """
        Returns `title`.

        This property also exists in `User`, where it returns the first name and last name
        concatenated.

        .. code-block:: python

            print(message.chat.full_name):
        """
        return self.title
