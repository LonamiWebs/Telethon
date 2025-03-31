from typing import Optional, Tuple
from enum import IntEnum
from ..tl.types import InputPeerUser, InputPeerChat, InputPeerChannel
import struct

class SessionState:
    """
    Stores the information needed to fetch updates and about the current user.

    * user_id: 64-bit number representing the user identifier.
    * dc_id: 32-bit number relating to the datacenter identifier where the user is.
    * bot: is the logged-in user a bot?
    * pts: 64-bit number holding the state needed to fetch updates.
    * qts: alternative 64-bit number holding the state needed to fetch updates.
    * date: 64-bit number holding the date needed to fetch updates.
    * seq: 64-bit-number holding the sequence number needed to fetch updates.
    * takeout_id: 64-bit-number holding the identifier of the current takeout session.

    Note that some of the numbers will only use 32 out of the 64 available bits.
    However, for future-proofing reasons, we recommend you pretend they are 64-bit long.
    """
    __slots__ = ('user_id', 'dc_id', 'bot', 'pts', 'qts', 'date', 'seq', 'takeout_id')

    def __init__(
        self,
        user_id: int,
        dc_id: int,
        bot: bool,
        pts: int,
        qts: int,
        date: int,
        seq: int,
        takeout_id: Optional[int]
    ):
        self.user_id = user_id
        self.dc_id = dc_id
        self.bot = bot
        self.pts = pts
        self.qts = qts
        self.date = date
        self.seq = seq
        self.takeout_id = takeout_id

    def __repr__(self):
        return repr({k: getattr(self, k) for k in self.__slots__})


class ChannelState:
    """
    Stores the information needed to fetch updates from a channel.

    * channel_id: 64-bit number representing the channel identifier.
    * pts: 64-bit number holding the state needed to fetch updates.
    """
    __slots__ = ('channel_id', 'pts')

    def __init__(
        self,
        channel_id: int,
        pts: int,
    ):
        self.channel_id = channel_id
        self.pts = pts

    def __repr__(self):
        return repr({k: getattr(self, k) for k in self.__slots__})


class EntityType(IntEnum):
    """
    You can rely on the type value to be equal to the ASCII character one of:

    * 'U' (85): this entity belongs to a :tl:`User` who is not a ``bot``.
    * 'B' (66): this entity belongs to a :tl:`User` who is a ``bot``.
    * 'G' (71): this entity belongs to a small group :tl:`Chat`.
    * 'C' (67): this entity belongs to a standard broadcast :tl:`Channel`.
    * 'M' (77): this entity belongs to a megagroup :tl:`Channel`.
    * 'E' (69): this entity belongs to an "enormous" "gigagroup" :tl:`Channel`.
    """
    USER = ord('U')
    BOT = ord('B')
    GROUP = ord('G')
    CHANNEL = ord('C')
    MEGAGROUP = ord('M')
    GIGAGROUP = ord('E')

    def canonical(self):
        """
        Return the canonical version of this type.
        """
        return _canon_entity_types[self]


_canon_entity_types = {
    EntityType.USER: EntityType.USER,
    EntityType.BOT: EntityType.USER,
    EntityType.GROUP: EntityType.GROUP,
    EntityType.CHANNEL: EntityType.CHANNEL,
    EntityType.MEGAGROUP: EntityType.CHANNEL,
    EntityType.GIGAGROUP: EntityType.CHANNEL,
}


class Entity:
    """
    Stores the information needed to use a certain user, chat or channel with the API.

    * ty: 8-bit number indicating the type of the entity (of type `EntityType`).
    * id: 64-bit number uniquely identifying the entity among those of the same type.
    * hash: 64-bit signed number needed to use this entity with the API.

    The string representation of this class is considered to be stable, for as long as
    Telegram doesn't need to add more fields to the entities. It can also be converted
    to bytes with ``bytes(entity)``, for a more compact representation.
    """
    __slots__ = ('ty', 'id', 'hash')

    def __init__(
        self,
        ty: EntityType,
        id: int,
        hash: int
    ):
        self.ty = ty
        self.id = id
        self.hash = hash

    @property
    def is_user(self):
        """
        ``True`` if the entity is either a user or a bot.
        """
        return self.ty in (EntityType.USER, EntityType.BOT)

    @property
    def is_group(self):
        """
        ``True`` if the entity is a small group chat or `megagroup`_.

        .. _megagroup: https://telegram.org/blog/supergroups5k
        """
        return self.ty in (EntityType.GROUP, EntityType.MEGAGROUP)

    @property
    def is_broadcast(self):
        """
        ``True`` if the entity is a broadcast channel or `broadcast group`_.

        .. _broadcast group: https://telegram.org/blog/autodelete-inv2#groups-with-unlimited-members
        """
        return self.ty in (EntityType.CHANNEL, EntityType.GIGAGROUP)

    @classmethod
    def from_str(cls, string: str):
        """
        Convert the string into an `Entity`.
        """
        try:
            ty, id, hash = string.split('.')
            ty, id, hash = ord(ty), int(id), int(hash)
        except AttributeError:
            raise TypeError(f'expected str, got {string!r}') from None
        except (TypeError, ValueError):
            raise ValueError(f'malformed entity str (must be T.id.hash), got {string!r}') from None

        return cls(EntityType(ty), id, hash)

    @classmethod
    def from_bytes(cls, blob):
        """
        Convert the bytes into an `Entity`.
        """
        try:
            ty, id, hash = struct.unpack('<Bqq', blob)
        except struct.error:
            raise ValueError(f'malformed entity data, got {blob!r}') from None

        return cls(EntityType(ty), id, hash)

    def __str__(self):
        return f'{chr(self.ty)}.{self.id}.{self.hash}'

    def __bytes__(self):
        return struct.pack('<Bqq', self.ty, self.id, self.hash)

    def _as_input_peer(self):
        if self.is_user:
            return InputPeerUser(self.id, self.hash)
        elif self.ty == EntityType.GROUP:
            return InputPeerChat(self.id)
        else:
            return InputPeerChannel(self.id, self.hash)

    def __repr__(self):
        return repr({k: getattr(self, k) for k in self.__slots__})
