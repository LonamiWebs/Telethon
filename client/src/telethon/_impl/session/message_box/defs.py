import base64
import logging
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Self, Union

from ...tl import abcs


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


class PtsInfo:
    __slots__ = ("pts", "pts_count", "entry")

    def __init__(self, entry: "Entry", pts: int, pts_count: int) -> None:
        self.pts = pts
        self.pts_count = pts_count
        self.entry = entry

    def __repr__(self) -> str:
        return (
            f"PtsInfo(pts={self.pts}, pts_count={self.pts_count}, entry={self.entry})"
        )


class State:
    __slots__ = ("pts", "deadline")

    def __init__(
        self,
        pts: int,
        deadline: float,
    ) -> None:
        self.pts = pts
        self.deadline = deadline

    def __repr__(self) -> str:
        return f"State(pts={self.pts}, deadline={self.deadline})"


class PossibleGap:
    __slots__ = ("deadline", "updates")

    def __init__(
        self,
        deadline: float,
        updates: List[abcs.Update],
    ) -> None:
        self.deadline = deadline
        self.updates = updates

    def __repr__(self) -> str:
        return (
            f"PossibleGap(deadline={self.deadline}, update_count={len(self.updates)})"
        )


class PrematureEndReason(Enum):
    TEMPORARY_SERVER_ISSUES = "tmp"
    BANNED = "ban"


class Gap(ValueError):
    def __repr__(self) -> str:
        return "Gap()"


NO_SEQ = 0

NO_PTS = 0

# https://core.telegram.org/method/updates.getChannelDifference
BOT_CHANNEL_DIFF_LIMIT = 100000
USER_CHANNEL_DIFF_LIMIT = 100

POSSIBLE_GAP_TIMEOUT = 0.5

# https://core.telegram.org/api/updates
NO_UPDATES_TIMEOUT = 15 * 60

ENTRY_ACCOUNT: Literal["ACCOUNT"] = "ACCOUNT"
ENTRY_SECRET: Literal["SECRET"] = "SECRET"
Entry = Union[Literal["ACCOUNT"], Literal["SECRET"], int]

# Python's logging doesn't define a TRACE level. Pick halfway between DEBUG and NOTSET.
# We don't define a name for this as libraries shouldn't do that though.
LOG_LEVEL_TRACE = (logging.DEBUG - logging.NOTSET) // 2
