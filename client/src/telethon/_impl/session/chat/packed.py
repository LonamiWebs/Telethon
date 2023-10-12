import struct
from enum import IntFlag
from typing import Optional, Self

from ...tl import abcs, types


class PackedType(IntFlag):
    """
    The type of a :class:`PackedChat`.
    """

    # bits: zero, has-access-hash, channel, broadcast, group, chat, user, bot
    USER = 0b0000_0010
    BOT = 0b0000_0011
    CHAT = 0b0000_0100
    MEGAGROUP = 0b0010_1000
    BROADCAST = 0b0011_0000
    GIGAGROUP = 0b0011_1000


class PackedChat:
    """
    A compact representation of a :term:`chat`.

    You can reuse it as many times as you want.

    You can call ``chat.pack()`` on :class:`~telethon.types.User`,
    :class:`~telethon.types.Group` or :class:`~telethon.types.Channel` to obtain it.

    .. seealso::

        :doc:`/concepts/chats`
    """

    __slots__ = ("ty", "id", "access_hash")

    def __init__(self, ty: PackedType, id: int, access_hash: Optional[int]) -> None:
        self.ty = ty
        self.id = id
        self.access_hash = access_hash

    def __bytes__(self) -> bytes:
        return struct.pack(
            "<Bqq",
            self.ty.value | (0 if self.access_hash is None else 0b0100_0000),
            self.id,
            self.access_hash or 0,
        )

    @classmethod
    def from_bytes(cls, data: bytes) -> Self:
        ty_byte, id, access_hash = struct.unpack("<Bqq", data)
        has_hash = (ty_byte & 0b0100_0000) != 0
        ty = PackedType(ty_byte & 0b0011_1111)
        return cls(ty, id, access_hash if has_hash else None)

    @property
    def hex(self) -> str:
        """
        Convenience property to convert to bytes and represent them as hexadecimal numbers:

        .. code-block::

            assert packed.hex == bytes(packed).hex()
        """
        return bytes(self).hex()

    def from_hex(cls, hex: str) -> Self:
        """
        Convenience method to convert hexadecimal numbers into bytes then passed to :meth:`from_bytes`:

        :param hex:
            Hexadecimal numbers to convert from.

        .. code-block::

            assert PackedChat.from_hex(packed.hex) == packed
        """
        return cls.from_bytes(bytes.fromhex(hex))

    def is_user(self) -> bool:
        return self.ty in (PackedType.USER, PackedType.BOT)

    def is_chat(self) -> bool:
        return self.ty in (PackedType.CHAT,)

    def is_channel(self) -> bool:
        return self.ty in (
            PackedType.MEGAGROUP,
            PackedType.BROADCAST,
            PackedType.GIGAGROUP,
        )

    def _to_peer(self) -> abcs.Peer:
        if self.is_user():
            return types.PeerUser(user_id=self.id)
        elif self.is_chat():
            return types.PeerChat(chat_id=self.id)
        elif self.is_channel():
            return types.PeerChannel(channel_id=self.id)
        else:
            raise RuntimeError("unexpected case")

    def _to_input_peer(self) -> abcs.InputPeer:
        if self.is_user():
            return types.InputPeerUser(
                user_id=self.id, access_hash=self.access_hash or 0
            )
        elif self.is_chat():
            return types.InputPeerChat(chat_id=self.id)
        elif self.is_channel():
            return types.InputPeerChannel(
                channel_id=self.id, access_hash=self.access_hash or 0
            )
        else:
            raise RuntimeError("unexpected case")

    def _to_input_user(self) -> types.InputUser:
        if self.is_user():
            return types.InputUser(user_id=self.id, access_hash=self.access_hash or 0)
        else:
            raise TypeError("chat is not a user")

    def _to_chat_id(self) -> int:
        if self.is_chat():
            return self.id
        else:
            raise TypeError("chat is not a group")

    def _to_input_channel(self) -> types.InputChannel:
        if self.is_channel():
            return types.InputChannel(
                channel_id=self.id, access_hash=self.access_hash or 0
            )
        else:
            raise TypeError("chat is not a channel")

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, self.__class__):
            return NotImplemented
        return (
            self.ty == other.ty
            and self.id == other.id
            and self.access_hash == other.access_hash
        )

    def __str__(self) -> str:
        return f"PackedChat.{self.ty.name}({self.id})"
