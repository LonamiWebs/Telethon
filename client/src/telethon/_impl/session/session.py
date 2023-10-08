import base64
from typing import Any, Dict, List, Optional, Self


class DataCenter:
    """
    Data-center information.

    :param id: See below.
    :param addr: See below.
    :param auth: See below.
    """

    __slots__ = ("id", "addr", "auth")

    def __init__(self, *, id: int, addr: str, auth: Optional[bytes]) -> None:
        self.id = id
        "The DC identifier."
        self.addr = addr
        "The server address of the DC, in ``'ip:port'`` format."
        self.auth = auth
        "Authentication key to encrypt communication with."


class User:
    """
    Information about the logged-in user.

    :param id: See below.
    :param dc: See below.
    :param bot: See below.
    :param username: See below.
    """

    __slots__ = ("id", "dc", "bot", "username")

    def __init__(self, *, id: int, dc: int, bot: bool, username: Optional[str]) -> None:
        self.id = id
        "User identifier."
        self.dc = dc
        'Data-center identifier of the user\'s "home" DC.'
        self.bot = bot
        ":data:`True` if the user is from a bot account."
        self.username = username
        "User's primary username."


class ChannelState:
    """
    Update state for a channel.

    :param id: See below.
    :param pts: See below.
    """

    __slots__ = ("id", "pts")

    def __init__(self, *, id: int, pts: int) -> None:
        self.id = id
        "The channel identifier."
        self.pts = pts
        "The channel's partial sequence number."


class UpdateState:
    """
    Update state for an account.

    :param pts: See below.
    :param qts: See below.
    :param date: See below.
    :param seq: See below.
    :param channels: See below.
    """

    __slots__ = (
        "pts",
        "qts",
        "date",
        "seq",
        "channels",
    )

    def __init__(
        self,
        *,
        pts: int,
        qts: int,
        date: int,
        seq: int,
        channels: List[ChannelState],
    ) -> None:
        self.pts = pts
        "The primary partial sequence number."
        self.qts = qts
        "The secondary partial sequence number."
        self.date = date
        "Date of the latest update sequence."
        self.seq = seq
        "The sequence number."
        self.channels = channels
        "Update state for channels."


class Session:
    """
    A Telethon :term:`session`.

    A session instance contains the required information to login into your
    Telegram account. **Never** give the saved session file to anyone else or
    make it public.

    Leaking the session file will grant a bad actor complete access to your
    account, including private conversations, groups you're part of and list
    of contacts (though not secret chats).

    If you think the session has been compromised, immediately terminate all
    sessions through an official Telegram client to revoke the authorization.

    :param dcs: See below.
    :param user: See below.
    :param state: See below.
    """

    VERSION = 1
    """
    Current version.

    Will be incremented if new fields are added.
    """

    __slots__ = ("dcs", "user", "state")

    def __init__(
        self,
        *,
        dcs: Optional[List[DataCenter]] = None,
        user: Optional[User] = None,
        state: Optional[UpdateState] = None,
    ):
        self.dcs = dcs or []
        "List of known data-centers."
        self.user = user
        "Information about the logged-in user."
        self.state = state
        "Update state."
