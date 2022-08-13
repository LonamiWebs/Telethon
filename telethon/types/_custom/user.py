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
from ..._sessions.types import Entity


if TYPE_CHECKING:
    from ..._misc import hints


def _fwd(field, doc):
    def fget(self):
        return getattr(self._user, field, None)

    def fset(self, value):
        object.__setattr__(self._user, field, value)

    return property(fget, fset, None, doc)


class BotInfo:
    @property
    def version(self):
        """
        Version number of this information, incremented whenever it changes.
        """
        return self._user.bot_info_version

    @property
    def chat_history_access(self):
        """
        `True` if the bot has privacy mode disabled via @BotFather and can see *all* messages of the group.
        """
        return self._user.bot_chat_history

    @property
    def private_only(self):
        """
        `True` if the bot cannot be added to group and can only be used in private messages.
        """
        return self._user.bot_nochats

    @property
    def inline_geo(self):
        """
        `True` if the bot can request the user's geolocation when used in @bot inline mode.
        """
        return self._user.bot_inline_geo

    @property
    def inline_placeholder(self):
        """
        The placeholder to show when using the @bot inline mode.
        """
        return self._user.bot_inline_placeholder

    def __init__(self, user):
        self._user = user


@dataclass(frozen=True)
class _TinyUser:
    __slots__ = ('id', 'access_hash')

    id: int
    access_hash: int


class User:
    """
    Represents a :tl:`User` (or :tl:`UserEmpty`, or :tl:`UserFull`) from the API.
    """

    id = _fwd('id', """
        The user identifier. This is the only property which will **always** be present.
    """)

    first_name = _fwd('first_name', """
        The user's first name. It will be ``None`` for deleted accounts.
    """)

    last_name = _fwd('last_name', """
        The user's last name. It can be ``None``.
    """)

    username = _fwd('username', """
        The user's @username. It can be ``None``.
    """)

    phone = _fwd('phone', """
        The user's phone number. It can be ``None`` if the user is not in your contacts or their
        privacy setting does not allow you to view the phone number.
    """)

    is_self = _fwd('is_self', """
        ``True`` if this user represents the logged-in account.
    """)

    bot = _fwd('bot', """
        ``True`` if this user is a bot created via @BotFather.
    """)

    contact = _fwd('contact', """
        ``True`` if this user is in the contact list of the logged-in account.
    """)

    mutual_contact = _fwd('mutual_contact', """
        ``True`` if this user is in the contact list of the logged-in account,
        and the user also has the logged-in account in their contact list.
    """)

    deleted = _fwd('deleted', """
        ``True`` if this user belongs to a deleted account.
    """)

    verified = _fwd('verified', """
        ``True`` if this user represents an official account verified by Telegram.
    """)

    restricted = _fwd('restricted', """
        `True` if the user has been restricted for some reason.
    """)

    support = _fwd('support', """
        ``True`` if this user belongs to an official account from Telegram Support.
    """)

    scam = _fwd('scam', """
        ``True`` if this user has been flagged as spam.
    """)

    fake = _fwd('fake', """
        ``True`` if this user has been flagged as fake.
    """)

    lang_code = _fwd('lang_code', """
        Language code of the user, if it's known.
    """)

    @property
    def restriction_reasons(self):
        """
        Returns a possibly-empty list of reasons why the chat is restricted to some platforms.
        """
        try:
            return self._user.restriction_reason or []
        except AttributeError:
            return []

    @property
    def bot_info(self):
        """
        Additional information about the user if it's a bot, `None` otherwise.
        """
        return BotInfo(self._user) if self.bot else None

    def __init__(self):
        raise TypeError('You cannot create User instances by hand!')

    @classmethod
    def _new(cls, client, user):
        self = cls.__new__(cls)
        self._client = client

        if isinstance(user, Entity):
            if not user.is_user:
                raise TypeError('Tried to construct User with non-user Entity')

            self._user = _TinyUser(user.id, user.hash)
        else:
            self._user = user

        self._full = None

        return self

    async def fetch(self, *, full=False):
        """
        Perform an API call to fetch fresh information about this user.

        Returns itself, but with the information fetched (allowing you to chain the call).

        If ``full`` is ``True``, the full information about the user will be fetched,
        which will include things like ``about``.
        """

        # sender - might just be hash
        # get sender - might be min
        # sender fetch - never min

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

    def download_profile_photo():
        # why'd you want to access photo? just do this
        pass

    def get_profile_photos():
        # this i can understand as you can pick other photos... sadly exposing raw api
        pass

    # TODO status, photo, and full properties

    @property
    def is_user(self):
        """
        Returns `True`.

        This property also exists in `Chat`, where it returns `False`.

        .. code-block:: python

            if message.sender.is_user:
                ...  # do stuff
        """
        return True

    @property
    def is_group(self):
        """
        Returns `False`.

        This property also exists in `Chat`, where it can return `True`.

        .. code-block:: python

            if message.sender.is_group:
                ...  # do stuff
        """
        return False

    @property
    def is_broadcast(self):
        """
        Returns `False`.

        This property also exists in `Chat`, where it can return `True`.

        .. code-block:: python

            if message.sender.is_broadcast:
                ...  # do stuff
        """
        return False

    @property
    def full_name(self):
        """
        Returns the user's full name (first name and last name concatenated).

        This property also exists in `Chat`, where it returns the title.

        .. code-block:: python

            print(message.sender.full_name):
        """
        return f'{self.first_name} {self.last_name}' if self.last_name else self.first_name
