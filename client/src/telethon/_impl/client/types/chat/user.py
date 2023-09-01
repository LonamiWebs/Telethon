from typing import List, Optional, Self

from ....session.chat.packed import PackedChat, PackedType
from ....tl import abcs, types
from ..meta import NoPublicConstructor


class RestrictionReason(metaclass=NoPublicConstructor):
    __slots__ = ("_raw",)

    def __init__(self, raw: types.RestrictionReason) -> None:
        self._raw = raw

    @classmethod
    def _from_raw(cls, reason: abcs.RestrictionReason) -> Self:
        assert isinstance(reason, types.RestrictionReason)
        return cls._create(reason)

    @property
    def platforms(self) -> List[str]:
        return self._raw.platform.split("-")

    @property
    def reason(self) -> str:
        return self._raw.reason

    @property
    def text(self) -> str:
        return self._raw.text


class User(metaclass=NoPublicConstructor):
    __slots__ = ("_raw",)

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
                )
            )
        elif isinstance(user, types.User):
            return cls._create(user)
        else:
            raise RuntimeError("unexpected case")

    @property
    def id(self) -> int:
        return self._raw.id

    def pack(self) -> Optional[PackedChat]:
        if self._raw.access_hash is not None:
            return PackedChat(
                ty=PackedType.BOT if self._raw.bot else PackedType.USER,
                id=self._raw.id,
                access_hash=self._raw.access_hash,
            )
        else:
            return None

    @property
    def first_name(self) -> str:
        return self._raw.first_name or ""

    @property
    def last_name(self) -> str:
        return self._raw.last_name or ""

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def username(self) -> Optional[str]:
        return self._raw.username

    @property
    def phone(self) -> Optional[str]:
        return self._raw.phone

    @property
    def bot(self) -> bool:
        return self._raw.bot

    @property
    def restriction_reasons(self) -> List[RestrictionReason]:
        return [
            RestrictionReason._from_raw(r) for r in (self._raw.restriction_reason or [])
        ]
