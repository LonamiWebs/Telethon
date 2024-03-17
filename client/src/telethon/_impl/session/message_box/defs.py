import logging
from enum import Enum
from typing import Literal

from ...tl import abcs

NO_DATE = 0  # used on adapted messages.affected* from lower layers
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
Entry = Literal["ACCOUNT", "SECRET"] | int

# Python's logging doesn't define a TRACE level. Pick halfway between DEBUG and NOTSET.
# We don't define a name for this as libraries shouldn't do that though.
LOG_LEVEL_TRACE = (logging.DEBUG - logging.NOTSET) // 2


class PtsInfo:
    __slots__ = ("pts", "pts_count", "entry")

    entry: Entry  # pyright needs this or it infers int | str

    def __init__(self, entry: Entry, pts: int, pts_count: int) -> None:
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
        updates: list[abcs.Update],
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
