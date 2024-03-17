from typing import Optional, Self

from ....session import PackedChat, PackedType
from ....tl import abcs, types
from ..meta import NoPublicConstructor
from .chat import Chat


class User(Chat, metaclass=NoPublicConstructor):
    """
    A user, representing either a bot account or an account created with a phone number.

    You can get a user from messages via :attr:`telethon.types.Message.sender`,
    or from methods such as :meth:`telethon.Client.resolve_username`.
    """

    def __init__(self, raw: types.User) -> None:
        self._raw = raw

    @classmethod
    def _from_raw(cls, user: abcs.User) -> Self:
        if isinstance(user, types.UserEmpty):
            return cls._create(
                types.User(
                    self=False,
                    contact=False,
                    mutual_contact=False,
                    deleted=False,
                    bot=False,
                    bot_chat_history=False,
                    bot_nochats=False,
                    verified=False,
                    restricted=False,
                    min=False,
                    bot_inline_geo=False,
                    support=False,
                    scam=False,
                    apply_min_photo=False,
                    fake=False,
                    bot_attach_menu=False,
                    premium=False,
                    attach_menu_enabled=False,
                    bot_can_edit=False,
                    close_friend=False,
                    stories_hidden=False,
                    stories_unavailable=False,
                    id=user.id,
                    access_hash=None,
                    first_name=None,
                    last_name=None,
                    username=None,
                    phone=None,
                    photo=None,
                    status=None,
                    bot_info_version=None,
                    restriction_reason=None,
                    bot_inline_placeholder=None,
                    lang_code=None,
                    emoji_status=None,
                    usernames=None,
                    stories_max_id=None,
                )
            )
        elif isinstance(user, types.User):
            return cls._create(user)
        else:
            raise RuntimeError("unexpected case")

    # region Overrides

    @property
    def id(self) -> int:
        return self._raw.id

    @property
    def name(self) -> str:
        """
        The user's full name.

        This property joins both the :attr:`first_name` and :attr:`last_name` into a single string.

        This property is always present, but may be the empty string.
        """
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def username(self) -> Optional[str]:
        return self._raw.username

    def pack(self) -> Optional[PackedChat]:
        if self._raw.access_hash is None:
            return None
        else:
            return PackedChat(
                ty=PackedType.BOT if self._raw.bot else PackedType.USER,
                id=self._raw.id,
                access_hash=self._raw.access_hash,
            )

    # endregion Overrides

    @property
    def first_name(self) -> str:
        return self._raw.first_name or ""

    @property
    def last_name(self) -> str:
        return self._raw.last_name or ""

    @property
    def phone(self) -> Optional[str]:
        return self._raw.phone

    @property
    def bot(self) -> bool:
        return self._raw.bot
