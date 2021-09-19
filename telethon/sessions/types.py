from typing import Optional, Tuple


class DataCenter:
    """
    Stores the information needed to connect to a datacenter.

    * id: 32-bit number representing the datacenter identifier as given by Telegram.
    * ipv4 and ipv6: 32-bit or 128-bit number storing the IP address of the datacenter.
    * port: 16-bit number storing the port number needed to connect to the datacenter.
    * bytes: arbitrary binary payload needed to authenticate to the datacenter.
    """
    __slots__ = ('id', 'ipv4', 'ipv6', 'port', 'auth')

    def __init__(
        self,
        id: int,
        ipv4: int,
        ipv6: Optional[int],
        port: int,
        auth: bytes
    ):
        self.id = id
        self.ipv4 = ipv4
        self.ipv6 = ipv6
        self.port = port
        self.auth = auth


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
        takeout_id: Optional[int],
    ):
        self.user_id = user_id
        self.dc_id = dc_id
        self.bot = bot
        self.pts = pts
        self.qts = qts
        self.date = date
        self.seq = seq


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
        pts: int
    ):
        self.channel_id = channel_id
        self.pts = pts


class Entity:
    """
    Stores the information needed to use a certain user, chat or channel with the API.

    * ty: 8-bit number indicating the type of the entity.
    * id: 64-bit number uniquely identifying the entity among those of the same type.
    * access_hash: 64-bit number needed to use this entity with the API.

    You can rely on the ``ty`` value to be equal to the ASCII character one of:

    * 'U' (85): this entity belongs to a :tl:`User` who is not a ``bot``.
    * 'B' (66): this entity belongs to a :tl:`User` who is a ``bot``.
    * 'G' (71): this entity belongs to a small group :tl:`Chat`.
    * 'C' (67): this entity belongs to a standard broadcast :tl:`Channel`.
    * 'M' (77): this entity belongs to a megagroup :tl:`Channel`.
    * 'E' (69): this entity belongs to an "enormous" "gigagroup" :tl:`Channel`.
    """
    __slots__ = ('ty', 'id', 'access_hash')

    USER = ord('U')
    BOT = ord('B')
    GROUP = ord('G')
    CHANNEL = ord('C')
    MEGAGROUP = ord('M')
    GIGAGROUP = ord('E')

    def __init__(
        self,
        ty: int,
        id: int,
        access_hash: int
    ):
        self.ty = ty
        self.id = id
        self.access_hash = access_hash


def canonical_entity_type(ty: int, *, _mapping={
    Entity.USER: Entity.USER,
    Entity.BOT: Entity.USER,
    Entity.GROUP: Entity.GROUP,
    Entity.CHANNEL: Entity.CHANNEL,
    Entity.MEGAGROUP: Entity.CHANNEL,
    Entity.GIGAGROUP: Entity.CHANNEL,
}) -> int:
    """
    Return the canonical version of an entity type.
    """
    try:
        return _mapping[ty]
    except KeyError:
        ty = chr(ty) if isinstance(ty, int) else ty
        raise ValueError(f'entity type {ty!r} is not valid')


def get_entity_type_group(ty: int, *, _mapping={
    Entity.USER: (Entity.USER, Entity.BOT),
    Entity.BOT: (Entity.USER, Entity.BOT),
    Entity.GROUP: (Entity.GROUP,),
    Entity.CHANNEL: (Entity.CHANNEL, Entity.MEGAGROUP, Entity.GIGAGROUP),
    Entity.MEGAGROUP: (Entity.CHANNEL, Entity.MEGAGROUP, Entity.GIGAGROUP),
    Entity.GIGAGROUP: (Entity.CHANNEL, Entity.MEGAGROUP, Entity.GIGAGROUP),
}) -> Tuple[int]:
    """
    Return the group where an entity type belongs to.
    """
    try:
        return _mapping[ty]
    except KeyError:
        ty = chr(ty) if isinstance(ty, int) else ty
        raise ValueError(f'entity type {ty!r} is not valid')
