import base64
from typing import Any, Dict, List, Optional, Self


class DataCenter:
    __slots__ = ("id", "addr", "auth")

    def __init__(self, *, id: int, addr: str, auth: Optional[bytes]) -> None:
        self.id = id
        self.addr = addr
        self.auth = auth


class User:
    __slots__ = ("id", "dc", "bot")

    def __init__(self, *, id: int, dc: int, bot: bool) -> None:
        self.id = id
        self.dc = dc
        self.bot = bot


class ChannelState:
    __slots__ = ("id", "pts")

    def __init__(self, *, id: int, pts: int) -> None:
        self.id = id
        self.pts = pts


class UpdateState:
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
        self.qts = qts
        self.date = date
        self.seq = seq
        self.channels = channels


class Session:
    """
    A Telethon session.

    A `Session` instance contains the required information to login into your
    Telegram account. **Never** give the saved session file to anyone else or
    make it public.

    Leaking the session file will grant a bad actor complete access to your
    account, including private conversations, groups you're part of and list
    of contacts (though not secret chats).

    If you think the session has been compromised, immediately terminate all
    sessions through an official Telegram client to revoke the authorization.
    """

    VERSION = 1

    __slots__ = ("dcs", "user", "state")

    def __init__(
        self,
        *,
        dcs: Optional[List[DataCenter]] = None,
        user: Optional[User] = None,
        state: Optional[UpdateState] = None,
    ):
        self.dcs = dcs or []
        self.user = user
        self.state = state

    def to_dict(self) -> Dict[str, Any]:
        return {
            "v": self.VERSION,
            "dcs": [
                {
                    "id": dc.id,
                    "addr": dc.addr,
                    "auth": base64.b64encode(dc.auth).decode("ascii")
                    if dc.auth
                    else None,
                }
                for dc in self.dcs
            ],
            "user": {
                "id": self.user.id,
                "dc": self.user.dc,
                "bot": self.user.bot,
            }
            if self.user
            else None,
            "state": {
                "pts": self.state.pts,
                "qts": self.state.qts,
                "date": self.state.date,
                "seq": self.state.seq,
                "channels": [
                    {"id": channel.id, "pts": channel.pts}
                    for channel in self.state.channels
                ],
            }
            if self.state
            else None,
        }

    @classmethod
    def from_dict(cls, dict: Dict[str, Any]) -> Self:
        version = dict["v"]
        if version != cls.VERSION:
            raise ValueError(
                f"cannot parse session format version {version} (expected {cls.VERSION})"
            )

        return cls(
            dcs=[
                DataCenter(
                    id=dc["id"],
                    addr=dc["addr"],
                    auth=base64.b64decode(dc["auth"])
                    if dc["auth"] is not None
                    else None,
                )
                for dc in dict["dcs"]
            ],
            user=User(
                id=dict["user"]["id"],
                dc=dict["user"]["dc"],
                bot=dict["user"]["bot"],
            )
            if dict["user"]
            else None,
            state=UpdateState(
                pts=dict["state"]["pts"],
                qts=dict["state"]["qts"],
                date=dict["state"]["date"],
                seq=dict["state"]["seq"],
                channels=[
                    ChannelState(id=channel["id"], pts=channel["pts"])
                    for channel in dict["state"]["channels"]
                ],
            )
            if dict["state"]
            else None,
        )
