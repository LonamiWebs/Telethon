import asyncio
import datetime
import logging
import time
from typing import Optional, Sequence

from ...tl import Request, abcs, functions, types
from ..chat import ChatHashCache
from ..session import ChannelState, UpdateState
from .adaptor import adapt, pts_info_from_update
from .defs import (
    BOT_CHANNEL_DIFF_LIMIT,
    ENTRY_ACCOUNT,
    ENTRY_SECRET,
    LOG_LEVEL_TRACE,
    NO_DATE,
    NO_PTS,
    NO_SEQ,
    NO_UPDATES_TIMEOUT,
    POSSIBLE_GAP_TIMEOUT,
    USER_CHANNEL_DIFF_LIMIT,
    Entry,
    Gap,
    PossibleGap,
    PrematureEndReason,
    State,
)


def next_updates_deadline() -> float:
    return asyncio.get_running_loop().time() + NO_UPDATES_TIMEOUT


def epoch() -> datetime.datetime:
    return datetime.datetime(*time.gmtime(0)[:6]).replace(tzinfo=datetime.timezone.utc)


# https://core.telegram.org/api/updates#message-related-event-sequences.
class MessageBox:
    __slots__ = (
        "_logger",
        "map",
        "date",
        "seq",
        "possible_gaps",
        "getting_diff_for",
        "next_deadline",
    )

    def __init__(
        self,
        *,
        base_logger: logging.Logger,
    ) -> None:
        self._logger = base_logger.getChild("messagebox")
        self.map: dict[Entry, State] = {}
        self.date = epoch()
        self.seq = NO_SEQ
        self.possible_gaps: dict[Entry, PossibleGap] = {}
        self.getting_diff_for: set[Entry] = set()
        self.next_deadline: Optional[Entry] = None

        if __debug__:
            self._trace("initialized")

    def _trace(self, msg: str, *args: object) -> None:
        # Calls to trace can't really be removed beforehand without some dark magic.
        # So every call to trace is prefixed with `if __debug__`` instead, to remove
        # it when using `python -O`. Probably unnecessary, but it's nice to avoid
        # paying the cost for something that is not used.
        self._logger.log(
            LOG_LEVEL_TRACE,
            "current state: seq=%r, date=%s, map=%r",
            self.seq,
            self.date.isoformat(),
            self.map,
        )
        self._logger.log(LOG_LEVEL_TRACE, msg, *args)

    def load(self, state: UpdateState) -> None:
        if __debug__:
            self._trace(
                "loading state: %r",
                state,
            )

        deadline = next_updates_deadline()

        self.map.clear()
        if state.pts != NO_SEQ:
            self.map[ENTRY_ACCOUNT] = State(pts=state.pts, deadline=deadline)
        if state.qts != NO_SEQ:
            self.map[ENTRY_SECRET] = State(pts=state.qts, deadline=deadline)
        self.map.update(
            (s.id, State(pts=s.pts, deadline=deadline)) for s in state.channels
        )

        self.date = datetime.datetime.fromtimestamp(
            state.date, tz=datetime.timezone.utc
        )
        self.seq = state.seq
        self.possible_gaps.clear()
        self.getting_diff_for.clear()
        self.next_deadline = ENTRY_ACCOUNT

    def reset(self) -> None:
        self.map.clear()
        self.date = epoch()
        self.seq = NO_SEQ
        self.possible_gaps.clear()
        self.getting_diff_for.clear()
        self.next_deadline = None

    def session_state(self) -> UpdateState:
        return UpdateState(
            pts=self.map[ENTRY_ACCOUNT].pts if ENTRY_ACCOUNT in self.map else NO_PTS,
            qts=self.map[ENTRY_SECRET].pts if ENTRY_SECRET in self.map else NO_PTS,
            date=int(self.date.timestamp()),
            seq=self.seq,
            channels=[
                ChannelState(id=int(entry), pts=state.pts)
                for entry, state in self.map.items()
                if entry not in (ENTRY_ACCOUNT, ENTRY_SECRET)
            ],
        )

    def is_empty(self) -> bool:
        return (self.map.get(ENTRY_ACCOUNT) or NO_PTS) == NO_PTS

    def check_deadlines(self) -> float:
        now = asyncio.get_running_loop().time()

        if self.getting_diff_for:
            return now

        default_deadline = next_updates_deadline()

        if self.possible_gaps:
            deadline = min(
                default_deadline, *(gap.deadline for gap in self.possible_gaps.values())
            )
        elif self.next_deadline in self.map:
            deadline = min(default_deadline, self.map[self.next_deadline].deadline)
        else:
            deadline = default_deadline

        if now >= deadline:
            self.getting_diff_for.update(
                entry
                for entry, gap in self.possible_gaps.items()
                if now >= gap.deadline
            )
            self.getting_diff_for.update(
                entry for entry, state in self.map.items() if now >= state.deadline
            )

            if __debug__:
                self._trace(
                    "deadlines met, now getting diff for: %r", self.getting_diff_for
                )

            for entry in self.getting_diff_for:
                self.possible_gaps.pop(entry, None)

        return deadline

    def reset_deadlines(self, entries: set[Entry], deadline: float) -> None:
        if not entries:
            return

        entry: Entry = ENTRY_ACCOUNT  # for pyright to know it's not unbound
        for entry in entries:
            if entry not in self.map:
                raise RuntimeError(
                    "Called reset_deadline on an entry for which we do not have state"
                )
            self.map[entry].deadline = deadline

        if self.next_deadline in entries:
            self.next_deadline = min(
                self.map.items(), key=lambda entry_state: entry_state[1].deadline
            )[0]
        elif (
            self.next_deadline in self.map
            and deadline < self.map[self.next_deadline].deadline
        ):
            self.next_deadline = entry

    def reset_channel_deadline(self, channel_id: int, timeout: Optional[float]) -> None:
        self.reset_deadlines(
            {channel_id},
            asyncio.get_running_loop().time() + (timeout or NO_UPDATES_TIMEOUT),
        )

    def set_state(self, state: abcs.updates.State) -> None:
        if __debug__:
            self._trace("setting state: %s", state)

        deadline = next_updates_deadline()
        assert isinstance(state, types.updates.State)
        self.map[ENTRY_ACCOUNT] = State(state.pts, deadline)
        self.map[ENTRY_SECRET] = State(state.qts, deadline)
        self.date = datetime.datetime.fromtimestamp(
            state.date, tz=datetime.timezone.utc
        )
        self.seq = state.seq

    def try_set_channel_state(self, id: int, pts: int) -> None:
        if __debug__:
            self._trace("trying to set channel=%r state: %r", id, pts)

        if id not in self.map:
            self.map[id] = State(pts=pts, deadline=next_updates_deadline())

    def try_begin_get_diff(self, entry: Entry, reason: str) -> None:
        if entry not in self.map:
            if entry in self.possible_gaps:
                raise RuntimeError(
                    "Should not have a possible_gap for an entry not in the state map"
                )
            return

        if __debug__:
            self._trace(
                "marking entry=%r as needing difference because: %s", entry, reason
            )
        self.getting_diff_for.add(entry)
        self.possible_gaps.pop(entry, None)

    def end_get_diff(self, entry: Entry) -> None:
        try:
            self.getting_diff_for.remove(entry)
        except KeyError:
            raise RuntimeError(
                "Called end_get_diff on an entry which was not getting diff for"
            )

        self.reset_deadlines({entry}, next_updates_deadline())
        assert (
            entry not in self.possible_gaps
        ), "gaps shouldn't be created while getting difference"

    def ensure_known_peer_hashes(
        self,
        updates: abcs.Updates,
        chat_hashes: ChatHashCache,
    ) -> None:
        if not chat_hashes.extend_from_updates(updates):
            can_recover = (
                not isinstance(updates, types.UpdateShort)
                or pts_info_from_update(updates.update) is not None
            )
            if can_recover:
                self.try_begin_get_diff(ENTRY_ACCOUNT, "missing hash")
                raise Gap

    # https://core.telegram.org/api/updates
    def process_updates(
        self,
        updates: abcs.Updates,
        chat_hashes: ChatHashCache,
    ) -> tuple[list[abcs.Update], Sequence[abcs.User], Sequence[abcs.Chat]]:
        result: list[abcs.Update] = []
        combined = adapt(updates, chat_hashes)

        if __debug__:
            self._trace(
                "processing updates with seq=%r, seq_start=%r, date=%r: %s",
                combined.seq,
                combined.seq_start,
                combined.date,
                updates,
            )

        if combined.seq_start != NO_SEQ:
            if self.seq + 1 > combined.seq_start:
                if __debug__:
                    self._trace(
                        "skipping updates as they should have already been handled"
                    )
                return result, combined.users, combined.chats
            elif self.seq + 1 < combined.seq_start:
                self.try_begin_get_diff(ENTRY_ACCOUNT, "detected gap")
                raise Gap

        def update_sort_key(update: abcs.Update) -> int:
            pts = pts_info_from_update(update)
            return pts.pts - pts.pts_count if pts else 0

        sorted_updates = list(sorted(combined.updates, key=update_sort_key))

        any_pts_applied = False
        reset_deadlines_for: set[Entry] = set()
        for update in sorted_updates:
            entry, applied = self.apply_pts_info(update)
            if entry is not None:
                reset_deadlines_for.add(entry)
            if applied is not None:
                result.append(applied)
                any_pts_applied |= entry is not None

        self.reset_deadlines(reset_deadlines_for, next_updates_deadline())

        if any_pts_applied:
            if __debug__:
                self._trace("updating seq as local pts was updated too")
            if combined.date != NO_DATE:
                self.date = datetime.datetime.fromtimestamp(
                    combined.date, tz=datetime.timezone.utc
                )
            if combined.seq != NO_SEQ:
                self.seq = combined.seq

        if self.possible_gaps:
            if __debug__:
                self._trace(
                    "trying to re-apply count=%r possible gaps", len(self.possible_gaps)
                )

            for key in list(self.possible_gaps.keys()):
                self.possible_gaps[key].updates.sort(key=update_sort_key)

                for _ in range(len(self.possible_gaps[key].updates)):
                    update = self.possible_gaps[key].updates.pop(0)
                    _, applied = self.apply_pts_info(update)
                    if applied is not None:
                        result.append(applied)
                        if __debug__:
                            self._trace(
                                "resolved gap with pts=%r: %s",
                                pts_info_from_update(applied),
                                applied,
                            )

            self.possible_gaps = {
                entry: gap for entry, gap in self.possible_gaps.items() if gap.updates
            }

        return result, combined.users, combined.chats

    def apply_pts_info(
        self,
        update: abcs.Update,
    ) -> tuple[Optional[Entry], Optional[abcs.Update]]:
        if isinstance(update, types.UpdateChannelTooLong):
            self.try_begin_get_diff(update.channel_id, "received updateChannelTooLong")
            return None, None

        pts = pts_info_from_update(update)
        if not pts:
            if __debug__:
                self._trace(
                    "no pts in update, so it can be applied in any order: %s", update
                )
            return None, update

        if pts.entry in self.getting_diff_for:
            if __debug__:
                self._trace(
                    "skipping update with pts=%r as its difference is being fetched",
                    pts,
                )
            return pts.entry, None

        if state := self.map.get(pts.entry):
            local_pts = state.pts
            if local_pts + pts.pts_count > pts.pts:
                if __debug__:
                    self._trace(
                        "skipping update since local-pts=%r > pts=%r: %s",
                        local_pts,
                        pts,
                        update,
                    )
                return pts.entry, None
            elif local_pts + pts.pts_count < pts.pts:
                if __debug__:
                    self._trace(
                        "possible gap since local-pts=%r < pts=%r: %s",
                        local_pts,
                        pts,
                        update,
                    )
                if pts.entry not in self.possible_gaps:
                    self.possible_gaps[pts.entry] = PossibleGap(
                        deadline=asyncio.get_running_loop().time()
                        + POSSIBLE_GAP_TIMEOUT,
                        updates=[],
                    )

                self.possible_gaps[pts.entry].updates.append(update)
                return pts.entry, None
            else:
                if __debug__:
                    self._trace(
                        "applying update pts since local-pts=%r = pts=%r: %s",
                        local_pts,
                        pts,
                        update,
                    )

        if pts.entry not in self.map:
            self.map[pts.entry] = State(
                pts=0,
                deadline=next_updates_deadline(),
            )
        self.map[pts.entry].pts = pts.pts

        return pts.entry, update

    def get_difference(self) -> Optional[Request[abcs.updates.Difference]]:
        for entry in (ENTRY_ACCOUNT, ENTRY_SECRET):
            if entry in self.getting_diff_for:
                if entry not in self.map:
                    raise RuntimeError(
                        "Should not try to get difference for an entry without known state"
                    )

                gd = functions.updates.get_difference(
                    pts=self.map[ENTRY_ACCOUNT].pts,
                    pts_limit=None,
                    pts_total_limit=None,
                    date=int(self.date.timestamp()),
                    qts=(
                        self.map[ENTRY_SECRET].pts
                        if ENTRY_SECRET in self.map
                        else NO_SEQ
                    ),
                    qts_limit=None,
                )
                if __debug__:
                    self._trace("requesting account difference: %s", gd)
                return gd

        return None

    def apply_difference(
        self,
        diff: abcs.updates.Difference,
        chat_hashes: ChatHashCache,
    ) -> tuple[list[abcs.Update], Sequence[abcs.User], Sequence[abcs.Chat]]:
        if __debug__:
            self._trace("applying account difference: %s", diff)

        finish: bool
        result: tuple[list[abcs.Update], Sequence[abcs.User], Sequence[abcs.Chat]]
        if isinstance(diff, types.updates.DifferenceEmpty):
            finish = True
            self.date = datetime.datetime.fromtimestamp(
                diff.date, tz=datetime.timezone.utc
            )
            self.seq = diff.seq
            result = [], [], []
        elif isinstance(diff, types.updates.Difference):
            chat_hashes.extend(diff.users, diff.chats)
            finish = True
            result = self.apply_difference_type(diff, chat_hashes)
        elif isinstance(diff, types.updates.DifferenceSlice):
            chat_hashes.extend(diff.users, diff.chats)
            finish = False
            result = self.apply_difference_type(
                types.updates.Difference(
                    new_messages=diff.new_messages,
                    new_encrypted_messages=diff.new_encrypted_messages,
                    other_updates=diff.other_updates,
                    chats=diff.chats,
                    users=diff.users,
                    state=diff.intermediate_state,
                ),
                chat_hashes,
            )
        elif isinstance(diff, types.updates.DifferenceTooLong):
            finish = True
            self.map[ENTRY_ACCOUNT].pts = diff.pts
            result = [], [], []
        else:
            raise RuntimeError("unexpected case")

        if finish:
            account = ENTRY_ACCOUNT in self.getting_diff_for
            secret = ENTRY_SECRET in self.getting_diff_for

            if not account and not secret:
                raise RuntimeError(
                    "Should not be applying the difference when neither account or secret was diff was active"
                )

            if account:
                self.end_get_diff(ENTRY_ACCOUNT)
            if secret:
                self.end_get_diff(ENTRY_SECRET)

        return result

    def apply_difference_type(
        self,
        diff: types.updates.Difference,
        chat_hashes: ChatHashCache,
    ) -> tuple[list[abcs.Update], Sequence[abcs.User], Sequence[abcs.Chat]]:
        state = diff.state
        assert isinstance(state, types.updates.State)
        self.map[ENTRY_ACCOUNT].pts = state.pts
        self.map[ENTRY_SECRET].pts = state.qts
        self.date = datetime.datetime.fromtimestamp(
            state.date, tz=datetime.timezone.utc
        )
        self.seq = state.seq

        updates, users, chats = self.process_updates(
            types.Updates(
                updates=diff.other_updates,
                users=diff.users,
                chats=diff.chats,
                date=int(epoch().timestamp()),
                seq=NO_SEQ,
            ),
            chat_hashes,
        )

        updates.extend(
            types.UpdateNewMessage(
                message=m,
                pts=NO_PTS,
                pts_count=0,
            )
            for m in diff.new_messages
        )
        updates.extend(
            types.UpdateNewEncryptedMessage(
                message=m,
                qts=NO_PTS,
            )
            for m in diff.new_encrypted_messages
        )

        return updates, users, chats

    def get_channel_difference(
        self,
        chat_hashes: ChatHashCache,
    ) -> Optional[Request[abcs.updates.ChannelDifference]]:
        for entry in self.getting_diff_for:
            if entry not in (ENTRY_ACCOUNT, ENTRY_SECRET):
                id = int(entry)
                break
        else:
            return None

        ref = chat_hashes.get(id)
        if ref:
            assert ref.authorization is not None
            channel = types.InputChannel(
                channel_id=ref.identifier,
                access_hash=ref.authorization,
            )
            if state := self.map.get(entry):
                gd = functions.updates.get_channel_difference(
                    force=False,
                    channel=channel,
                    filter=types.ChannelMessagesFilterEmpty(),
                    pts=state.pts,
                    limit=(
                        BOT_CHANNEL_DIFF_LIMIT
                        if chat_hashes.is_self_bot
                        else USER_CHANNEL_DIFF_LIMIT
                    ),
                )
                if __debug__:
                    self._trace("requesting channel difference: %s", gd)
                return gd
            else:
                raise RuntimeError(
                    "should not try to get difference for an entry without known state"
                )
        else:
            self.end_get_diff(entry)
            self.map.pop(entry, None)
            return None

    def apply_channel_difference(
        self,
        channel_id: int,
        diff: abcs.updates.ChannelDifference,
        chat_hashes: ChatHashCache,
    ) -> tuple[list[abcs.Update], Sequence[abcs.User], Sequence[abcs.Chat]]:
        entry: Entry = channel_id
        if __debug__:
            self._trace("applying channel=%r difference: %s", entry, diff)

        self.possible_gaps.pop(entry, None)

        if isinstance(diff, types.updates.ChannelDifferenceEmpty):
            assert diff.final
            self.end_get_diff(entry)
            self.map[entry].pts = diff.pts
            return [], [], []
        elif isinstance(diff, types.updates.ChannelDifferenceTooLong):
            chat_hashes.extend(diff.users, diff.chats)

            assert diff.final
            if isinstance(diff.dialog, types.Dialog):
                assert diff.dialog.pts is not None
                self.map[entry].pts = diff.dialog.pts
            else:
                raise RuntimeError("unexpected type on ChannelDifferenceTooLong")
            self.reset_channel_deadline(channel_id, diff.timeout)
            return [], [], []
        elif isinstance(diff, types.updates.ChannelDifference):
            chat_hashes.extend(diff.users, diff.chats)

            if diff.final:
                self.end_get_diff(entry)

            self.map[entry].pts = diff.pts
            updates, users, chats = self.process_updates(
                types.Updates(
                    updates=diff.other_updates,
                    users=diff.users,
                    chats=diff.chats,
                    date=int(epoch().timestamp()),
                    seq=NO_SEQ,
                ),
                chat_hashes,
            )

            updates.extend(
                types.UpdateNewChannelMessage(
                    message=m,
                    pts=NO_PTS,
                    pts_count=0,
                )
                for m in diff.new_messages
            )
            self.reset_channel_deadline(channel_id, None)

            return updates, users, chats
        else:
            raise RuntimeError("unexpected case")

    def end_channel_difference(
        self, channel_id: int, reason: PrematureEndReason
    ) -> None:
        entry: Entry = channel_id
        if __debug__:
            self._trace("ending channel=%r difference: %s", entry, reason)

        if reason == PrematureEndReason.TEMPORARY_SERVER_ISSUES:
            self.possible_gaps.pop(entry, None)
            self.end_get_diff(entry)
        elif reason == PrematureEndReason.BANNED:
            self.possible_gaps.pop(entry, None)
            self.end_get_diff(entry)
            del self.map[entry]
        else:
            raise RuntimeError("unknown reason to end channel difference")
