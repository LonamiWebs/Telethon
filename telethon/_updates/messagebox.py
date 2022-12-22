"""
This module deals with correct handling of updates, including gaps, and knowing when the code
should "get difference" (the set of updates that the client should know by now minus the set
of updates that it actually knows).

Each chat has its own [`Entry`] in the [`MessageBox`] (this `struct` is the "entry point").
At any given time, the message box may be either getting difference for them (entry is in
[`MessageBox::getting_diff_for`]) or not. If not getting difference, a possible gap may be
found for the updates (entry is in [`MessageBox::possible_gaps`]). Otherwise, the entry is
on its happy path.

Gaps are cleared when they are either resolved on their own (by waiting for a short time)
or because we got the difference for the corresponding entry.

While there are entries for which their difference must be fetched,
[`MessageBox::check_deadlines`] will always return [`Instant::now`], since "now" is the time
to get the difference.
"""
import asyncio
import datetime
import time
import logging
from enum import Enum
from .session import SessionState, ChannelState
from ..tl import types as tl, functions as fn
from ..helpers import get_running_loop


# Telegram sends `seq` equal to `0` when "it doesn't matter", so we use that value too.
NO_SEQ = 0

# See https://core.telegram.org/method/updates.getChannelDifference.
BOT_CHANNEL_DIFF_LIMIT = 100000
USER_CHANNEL_DIFF_LIMIT = 100

# > It may be useful to wait up to 0.5 seconds
POSSIBLE_GAP_TIMEOUT = 0.5

# After how long without updates the client will "timeout".
#
# When this timeout occurs, the client will attempt to fetch updates by itself, ignoring all the
# updates that arrive in the meantime. After all updates are fetched when this happens, the
# client will resume normal operation, and the timeout will reset.
#
# Documentation recommends 15 minutes without updates (https://core.telegram.org/api/updates).
NO_UPDATES_TIMEOUT = 15 * 60

# Entry "enum".
# Account-wide `pts` includes private conversations (one-to-one) and small group chats.
ENTRY_ACCOUNT = object()
# Account-wide `qts` includes only "secret" one-to-one chats.
ENTRY_SECRET = object()
# Integers will be Channel-specific `pts`, and includes "megagroup", "broadcast" and "supergroup" channels.

# Python's logging doesn't define a TRACE level. Pick halfway between DEBUG and NOTSET.
# We don't define a name for this as libraries shouldn't do that though.
LOG_LEVEL_TRACE = (logging.DEBUG - logging.NOTSET) // 2

_sentinel = object()

def next_updates_deadline():
    return get_running_loop().time() + NO_UPDATES_TIMEOUT


class GapError(ValueError):
    def __repr__(self):
        return 'GapError()'


class PrematureEndReason(Enum):
    TEMPORARY_SERVER_ISSUES = 'tmp'
    BANNED = 'ban'


# Represents the information needed to correctly handle a specific `tl::enums::Update`.
class PtsInfo:
    __slots__ = ('pts', 'pts_count', 'entry')

    def __init__(
        self,
        pts: int,
        pts_count: int,
        entry: object
    ):
        self.pts = pts
        self.pts_count = pts_count
        self.entry = entry

    @classmethod
    def from_update(cls, update):
        pts = getattr(update, 'pts', None)
        if pts:
            pts_count = getattr(update, 'pts_count', None) or 0
            try:
                entry = update.message.peer_id.channel_id
            except AttributeError:
                entry = getattr(update, 'channel_id', None) or ENTRY_ACCOUNT
            return cls(pts=pts, pts_count=pts_count, entry=entry)

        qts = getattr(update, 'qts', None)
        if qts:
            pts_count = 1 if isinstance(update, tl.UpdateNewEncryptedMessage) else 0
            return cls(pts=qts, pts_count=pts_count, entry=ENTRY_SECRET)

        return None

    def __repr__(self):
        if self.entry is ENTRY_ACCOUNT:
            entry = 'ENTRY_ACCOUNT'
        elif self.entry is ENTRY_SECRET:
            entry = 'ENTRY_SECRET'
        else:
            entry = self.entry
        return f'PtsInfo(pts={self.pts}, pts_count={self.pts_count}, entry={entry})'


# The state of a particular entry in the message box.
class State:
    __slots__ = ('pts', 'deadline')

    def __init__(
        self,
        # Current local persistent timestamp.
        pts: int,
        # Next instant when we would get the update difference if no updates arrived before then.
        deadline: float
    ):
        self.pts = pts
        self.deadline = deadline

    def __repr__(self):
        return f'State(pts={self.pts}, deadline={self.deadline})'


# > ### Recovering gaps
# > […] Manually obtaining updates is also required in the following situations:
# > • Loss of sync: a gap was found in `seq` / `pts` / `qts` (as described above).
# >   It may be useful to wait up to 0.5 seconds in this situation and abort the sync in case a new update
# >   arrives, that fills the gap.
#
# This is really easy to trigger by spamming messages in a channel (with as little as 3 members works), because
# the updates produced by the RPC request take a while to arrive (whereas the read update comes faster alone).
class PossibleGap:
    __slots__ = ('deadline', 'updates')

    def __init__(
        self,
        deadline: float,
        # Pending updates (those with a larger PTS, producing the gap which may later be filled).
        updates: list  # of updates
    ):
        self.deadline = deadline
        self.updates = updates

    def __repr__(self):
        return f'PossibleGap(deadline={self.deadline}, update_count={len(self.updates)})'


# Represents a "message box" (event `pts` for a specific entry).
#
# See https://core.telegram.org/api/updates#message-related-event-sequences.
class MessageBox:
    __slots__ = ('_log', 'map', 'date', 'seq', 'next_deadline', 'possible_gaps', 'getting_diff_for', 'reset_deadlines_for')

    def __init__(
        self,
        log,
        # Map each entry to their current state.
        map: dict = _sentinel,  # entry -> state

        # Additional fields beyond PTS needed by `ENTRY_ACCOUNT`.
        date: datetime.datetime = datetime.datetime(*time.gmtime(0)[:6]).replace(tzinfo=datetime.timezone.utc),
        seq: int = NO_SEQ,

        # Holds the entry with the closest deadline (optimization to avoid recalculating the minimum deadline).
        next_deadline: object = None,  # entry

        # Which entries have a gap and may soon trigger a need to get difference.
        #
        # If a gap is found, stores the required information to resolve it (when should it timeout and what updates
        # should be held in case the gap is resolved on its own).
        #
        # Not stored directly in `map` as an optimization (else we would need another way of knowing which entries have
        # a gap in them).
        possible_gaps: dict = _sentinel,  # entry -> possiblegap

        # For which entries are we currently getting difference.
        getting_diff_for: set = _sentinel,  # entry

        # Temporarily stores which entries should have their update deadline reset.
        # Stored in the message box in order to reuse the allocation.
        reset_deadlines_for: set = _sentinel  # entry
    ):
        self._log = log
        self.map = {} if map is _sentinel else map
        self.date = date
        self.seq = seq
        self.next_deadline = next_deadline
        self.possible_gaps = {} if possible_gaps is _sentinel else possible_gaps
        self.getting_diff_for = set() if getting_diff_for is _sentinel else getting_diff_for
        self.reset_deadlines_for = set() if reset_deadlines_for is _sentinel else reset_deadlines_for

        if __debug__:
            # Need this to tell them apart when printing the repr of the state map.
            # Could be done once at the global level, but that makes configuring logging
            # more annoying because it would need to be done before importing telethon.
            self._trace('ENTRY_ACCOUNT = %r; ENTRY_SECRET = %r', ENTRY_ACCOUNT, ENTRY_SECRET)
            self._trace('Created new MessageBox with map = %r, date = %r, seq = %r', self.map, self.date, self.seq)

    def _trace(self, msg, *args, **kwargs):
        # Calls to trace can't really be removed beforehand without some dark magic.
        # So every call to trace is prefixed with `if __debug__`` instead, to remove
        # it when using `python -O`. Probably unnecessary, but it's nice to avoid
        # paying the cost for something that is not used.
        self._log.log(LOG_LEVEL_TRACE, msg, *args, **kwargs)

    # region Creation, querying, and setting base state.

    def load(self, session_state, channel_states):
        """
        Create a [`MessageBox`] from a previously known update state.
        """
        if __debug__:
            self._trace('Loading MessageBox with session_state = %r, channel_states = %r', session_state, channel_states)

        deadline = next_updates_deadline()

        self.map.clear()
        if session_state.pts != NO_SEQ:
            self.map[ENTRY_ACCOUNT] = State(pts=session_state.pts, deadline=deadline)
        if session_state.qts != NO_SEQ:
            self.map[ENTRY_SECRET] = State(pts=session_state.qts, deadline=deadline)
        self.map.update((s.channel_id, State(pts=s.pts, deadline=deadline)) for s in channel_states)

        self.date = datetime.datetime.fromtimestamp(session_state.date).replace(tzinfo=datetime.timezone.utc)
        self.seq = session_state.seq
        self.next_deadline = ENTRY_ACCOUNT

    def session_state(self):
        """
        Return the current state.

        This should be used for persisting the state.
        """
        return dict(
            pts=self.map[ENTRY_ACCOUNT].pts if ENTRY_ACCOUNT in self.map else NO_SEQ,
            qts=self.map[ENTRY_SECRET].pts if ENTRY_SECRET in self.map else NO_SEQ,
            date=self.date,
            seq=self.seq,
        ), {id: state.pts for id, state in self.map.items() if isinstance(id, int)}

    def is_empty(self) -> bool:
        """
        Return true if the message box is empty and has no state yet.
        """
        return ENTRY_ACCOUNT not in self.map

    def check_deadlines(self):
        """
        Return the next deadline when receiving updates should timeout.

        If a deadline expired, the corresponding entries will be marked as needing to get its difference.
        While there are entries pending of getting their difference, this method returns the current instant.
        """
        now = get_running_loop().time()

        if self.getting_diff_for:
            return now

        deadline = next_updates_deadline()

        # Most of the time there will be zero or one gap in flight so finding the minimum is cheap.
        if self.possible_gaps:
            deadline = min(deadline, *(gap.deadline for gap in self.possible_gaps.values()))
        elif self.next_deadline in self.map:
            deadline = min(deadline, self.map[self.next_deadline].deadline)

        # asyncio's loop time precision only seems to be about 3 decimal places, so it's possible that
        # we find the same number again on repeated calls. Without the "or equal" part we would log the
        # timeout for updates several times (it also makes sense to get difference if now is the deadline).
        if now >= deadline:
            # Check all expired entries and add them to the list that needs getting difference.
            self.getting_diff_for.update(entry for entry, gap in self.possible_gaps.items() if now > gap.deadline)
            self.getting_diff_for.update(entry for entry, state in self.map.items() if now > state.deadline)

            if __debug__:
                self._trace('Deadlines met, now getting diff for %r', self.getting_diff_for)

            # When extending `getting_diff_for`, it's important to have the moral equivalent of
            # `begin_get_diff` (that is, clear possible gaps if we're now getting difference).
            for entry in self.getting_diff_for:
                self.possible_gaps.pop(entry, None)

        return deadline

    # Reset the deadline for the periods without updates for a given entry.
    #
    # It also updates the next deadline time to reflect the new closest deadline.
    def reset_deadline(self, entry, deadline):
        if entry not in self.map:
            raise RuntimeError('Called reset_deadline on an entry for which we do not have state')
        self.map[entry].deadline = deadline

        if self.next_deadline == entry:
            # If the updated deadline was the closest one, recalculate the new minimum.
            self.next_deadline = min(self.map.items(), key=lambda entry_state: entry_state[1].deadline)[0]
        elif self.next_deadline in self.map and deadline < self.map[self.next_deadline].deadline:
            # If the updated deadline is smaller than the next deadline, change the next deadline to be the new one.
            self.next_deadline = entry
        # else an unrelated deadline was updated, so the closest one remains unchanged.

    # Convenience to reset a channel's deadline, with optional timeout.
    def reset_channel_deadline(self, channel_id, timeout):
        self.reset_deadline(channel_id, get_running_loop().time() + (timeout or NO_UPDATES_TIMEOUT))

    # Reset all the deadlines in `reset_deadlines_for` and then empty the set.
    def apply_deadlines_reset(self):
        next_deadline = next_updates_deadline()

        reset_deadlines_for = self.reset_deadlines_for
        self.reset_deadlines_for = set()  # "move" the set to avoid self.reset_deadline() from touching it during iter

        for entry in reset_deadlines_for:
            self.reset_deadline(entry, next_deadline)

        reset_deadlines_for.clear()  # reuse allocation, the other empty set was a temporary dummy value
        self.reset_deadlines_for = reset_deadlines_for

    # Sets the update state.
    #
    # Should be called right after login if [`MessageBox::new`] was used, otherwise undesirable
    # updates will be fetched.
    def set_state(self, state, reset=True):
        if __debug__:
            self._trace('Setting state %s', state)

        deadline = next_updates_deadline()

        if state.pts != NO_SEQ or not reset:
            self.map[ENTRY_ACCOUNT] = State(pts=state.pts, deadline=deadline)
        else:
            self.map.pop(ENTRY_ACCOUNT, None)

        # Telegram seems to use the `qts` for bot accounts, but while applying difference,
        # it might be reset back to 0. See issue #3873 for more details.
        #
        # During login, a value of zero would mean the `pts` is unknown,
        # so the map shouldn't contain that entry.
        # But while applying difference, if the value is zero, it (probably)
        # truly means that's what should be used (hence the `reset` flag).
        if state.qts != NO_SEQ or not reset:
            self.map[ENTRY_SECRET] = State(pts=state.qts, deadline=deadline)
        else:
            self.map.pop(ENTRY_SECRET, None)

        self.date = state.date
        self.seq = state.seq

    # Like [`MessageBox::set_state`], but for channels. Useful when getting dialogs.
    #
    # The update state will only be updated if no entry was known previously.
    def try_set_channel_state(self, id, pts):
        if __debug__:
            self._trace('Trying to set channel state for %r: %r', id, pts)

        if id not in self.map:
            self.map[id] = State(pts=pts, deadline=next_updates_deadline())

    # Try to begin getting difference for the given entry.
    # Fails if the entry does not have a previously-known state that can be used to get its difference.
    #
    # Clears any previous gaps.
    def try_begin_get_diff(self, entry):
        if entry not in self.map:
            # Won't actually be able to get difference for this entry if we don't have a pts to start off from.
            if entry in self.possible_gaps:
                raise RuntimeError('Should not have a possible_gap for an entry not in the state map')

            # TODO it would be useful to log when this happens
            return

        self.getting_diff_for.add(entry)
        self.possible_gaps.pop(entry, None)

    # Finish getting difference for the given entry.
    #
    # It also resets the deadline.
    def end_get_diff(self, entry):
        try:
            self.getting_diff_for.remove(entry)
        except KeyError:
            raise RuntimeError('Called end_get_diff on an entry which was not getting diff for')

        self.reset_deadline(entry, next_updates_deadline())
        assert entry not in self.possible_gaps, "gaps shouldn't be created while getting difference"

    # endregion Creation, querying, and setting base state.

    # region "Normal" updates flow (processing and detection of gaps).

    # Process an update and return what should be done with it.
    #
    # Updates corresponding to entries for which their difference is currently being fetched
    # will be ignored. While according to the [updates' documentation]:
    #
    # > Implementations [have] to postpone updates received via the socket while
    # > filling gaps in the event and `Update` sequences, as well as avoid filling
    # > gaps in the same sequence.
    #
    # In practice, these updates should have also been retrieved through getting difference.
    #
    # [updates documentation] https://core.telegram.org/api/updates
    def process_updates(
        self,
        updates,
        chat_hashes,
        result,  # out list of updates; returns list of user, chat, or raise if gap
    ):
        if __debug__:
            self._trace('Processing updates %s', updates)

        date = getattr(updates, 'date', None)
        if date is None:
            # updatesTooLong is the only one with no date (we treat it as a gap)
            self.try_begin_get_diff(ENTRY_ACCOUNT)
            raise GapError

        # v1 has never sent updates produced by the client itself to the handlers.
        # However proper update handling requires those to be processed.
        # This is an ugly workaround for that.
        self_outgoing = getattr(updates, '_self_outgoing', False)
        real_result = result
        result = []

        seq = getattr(updates, 'seq', None) or NO_SEQ
        seq_start = getattr(updates, 'seq_start', None) or seq
        users = getattr(updates, 'users', None) or []
        chats = getattr(updates, 'chats', None) or []

        # updateShort is the only update which cannot be dispatched directly but doesn't have 'updates' field
        updates = getattr(updates, 'updates', None) or [updates.update if isinstance(updates, tl.UpdateShort) else updates]

        for u in updates:
            u._self_outgoing = self_outgoing

        # > For all the other [not `updates` or `updatesCombined`] `Updates` type constructors
        # > there is no need to check `seq` or change a local state.
        if seq_start != NO_SEQ:
            if self.seq + 1 > seq_start:
                # Skipping updates that were already handled
                return (users, chats)
            elif self.seq + 1 < seq_start:
                # Gap detected
                self.try_begin_get_diff(ENTRY_ACCOUNT)
                raise GapError
            # else apply

            self.date = date
            if seq != NO_SEQ:
                self.seq = seq

        def _sort_gaps(update):
            pts = PtsInfo.from_update(update)
            return pts.pts - pts.pts_count if pts else 0

        # Telegram can send updates out of order (e.g. ReadChannelInbox first
        # and then NewChannelMessage, both with the same pts, but the count is
        # 0 and 1 respectively).
        #
        # We can't know beforehand if this would cause issues (i.e. if any of
        # the updates is the first one we get to know about a specific channel)
        # (other than doing a pre-scan to check if any has info about an entry
        # we lack), so instead we sort preemptively. As a bonus there's less
        # likelyhood of "possible gaps" by doing this.
        # TODO give this more thought, perhaps possible gaps can't happen at all
        #      (not ones which would be resolved by sorting anyway)
        result.extend(filter(None, (
            self.apply_pts_info(u, reset_deadline=True) for u in sorted(updates, key=_sort_gaps))))

        self.apply_deadlines_reset()

        if self.possible_gaps:
            # For each update in possible gaps, see if the gap has been resolved already.
            for key in list(self.possible_gaps.keys()):
                self.possible_gaps[key].updates.sort(key=_sort_gaps)

                for _ in range(len(self.possible_gaps[key].updates)):
                    update = self.possible_gaps[key].updates.pop(0)

                    # If this fails to apply, it will get re-inserted at the end.
                    # All should fail, so the order will be preserved (it would've cycled once).
                    update = self.apply_pts_info(update, reset_deadline=False)
                    if update:
                        result.append(update)

            # Clear now-empty gaps.
            self.possible_gaps = {entry: gap for entry, gap in self.possible_gaps.items() if gap.updates}

        real_result.extend(u for u in result if not u._self_outgoing)

        return (users, chats)

    # Tries to apply the input update if its `PtsInfo` follows the correct order.
    #
    # If the update can be applied, it is returned; otherwise, the update is stored in a
    # possible gap (unless it was already handled or would be handled through getting
    # difference) and `None` is returned.
    def apply_pts_info(
        self,
        update,
        *,
        reset_deadline,
    ):
        # This update means we need to call getChannelDifference to get the updates from the channel
        if isinstance(update, tl.UpdateChannelTooLong):
            self.try_begin_get_diff(update.channel_id)
            return None

        pts = PtsInfo.from_update(update)
        if not pts:
            # No pts means that the update can be applied in any order.
            return update

        # As soon as we receive an update of any form related to messages (has `PtsInfo`),
        # the "no updates" period for that entry is reset.
        #
        # Build the `HashSet` to avoid calling `reset_deadline` more than once for the same entry.
        #
        # By the time this method returns, self.map will have an entry for which we can reset its deadline.
        if reset_deadline:
            self.reset_deadlines_for.add(pts.entry)

        if pts.entry in self.getting_diff_for:
            # Note: early returning here also prevents gap from being inserted (which they should
            # not be while getting difference).
            return None

        if pts.entry in self.map:
            local_pts = self.map[pts.entry].pts
            if local_pts + pts.pts_count > pts.pts:
                # Ignore
                return None
            elif local_pts + pts.pts_count < pts.pts:
                # Possible gap
                # TODO store chats too?
                if pts.entry not in self.possible_gaps:
                    self.possible_gaps[pts.entry] = PossibleGap(
                        deadline=get_running_loop().time() + POSSIBLE_GAP_TIMEOUT,
                        updates=[]
                    )

                self.possible_gaps[pts.entry].updates.append(update)
                return None
            else:
                # Apply
                pass

        # In a channel, we may immediately receive:
        # * ReadChannelInbox (pts = X, pts_count = 0)
        # * NewChannelMessage (pts = X, pts_count = 1)
        #
        # Notice how both `pts` are the same. If they were to be applied out of order, the first
        # one however would've triggered a gap because `local_pts` + `pts_count` of 0 would be
        # less than `remote_pts`. So there is no risk by setting the `local_pts` to match the
        # `remote_pts` here of missing the new message.
        #
        # The message would however be lost if we initialized the pts with the first one, since
        # the second one would appear "already handled". To prevent this we set the pts to be
        # one less when the count is 0 (which might be wrong and trigger a gap later on, but is
        # unlikely). This will prevent us from losing updates in the unlikely scenario where these
        # two updates arrive in different packets (and therefore couldn't be sorted beforehand).
        if pts.entry in self.map:
            self.map[pts.entry].pts = pts.pts
        else:
            # When a chat is migrated to a megagroup, the first update can be a `ReadChannelInbox`
            # with `pts = 1, pts_count = 0` followed by a `NewChannelMessage` with `pts = 2, pts_count=1`.
            # Note how the `pts` for the message is 2 and not 1 unlike the case described before!
            # This is likely because the `pts` cannot be 0 (or it would fail with PERSISTENT_TIMESTAMP_EMPTY),
            # which forces the first update to be 1. But if we got difference with 1 and the second update
            # also used 1, we would miss it, so Telegram probably uses 2 to work around that.
            self.map[pts.entry] = State(
                pts=(pts.pts - (0 if pts.pts_count else 1)) or 1,
                deadline=next_updates_deadline()
            )

        return update

    # endregion "Normal" updates flow (processing and detection of gaps).

    # region Getting and applying account difference.

    # Return the request that needs to be made to get the difference, if any.
    def get_difference(self):
        for entry in (ENTRY_ACCOUNT, ENTRY_SECRET):
            if entry in self.getting_diff_for:
                if entry not in self.map:
                    raise RuntimeError('Should not try to get difference for an entry without known state')

                gd = fn.updates.GetDifferenceRequest(
                    pts=self.map[ENTRY_ACCOUNT].pts,
                    pts_total_limit=None,
                    date=self.date,
                    qts=self.map[ENTRY_SECRET].pts if ENTRY_SECRET in self.map else NO_SEQ,
                )
                if __debug__:
                    self._trace('Requesting account difference %s', gd)
                return gd

        return None

    # Similar to [`MessageBox::process_updates`], but using the result from getting difference.
    def apply_difference(
        self,
        diff,
        chat_hashes,
    ):
        if __debug__:
            self._trace('Applying account difference %s', diff)

        finish = None
        result = None

        if isinstance(diff, tl.updates.DifferenceEmpty):
            finish = True
            self.date = diff.date
            self.seq = diff.seq
            result = [], [], []
        elif isinstance(diff, tl.updates.Difference):
            finish = True
            chat_hashes.extend(diff.users, diff.chats)
            result = self.apply_difference_type(diff, chat_hashes)
        elif isinstance(diff, tl.updates.DifferenceSlice):
            finish = False
            chat_hashes.extend(diff.users, diff.chats)
            result = self.apply_difference_type(diff, chat_hashes)
        elif isinstance(diff, tl.updates.DifferenceTooLong):
            finish = True
            self.map[ENTRY_ACCOUNT].pts = diff.pts  # the deadline will be reset once the diff ends
            result = [], [], []

        if finish:
            account = ENTRY_ACCOUNT in self.getting_diff_for
            secret = ENTRY_SECRET in self.getting_diff_for

            if not account and not secret:
                raise RuntimeError('Should not be applying the difference when neither account or secret was diff was active')

            # Both may be active if both expired at the same time.
            if account:
                self.end_get_diff(ENTRY_ACCOUNT)
            if secret:
                self.end_get_diff(ENTRY_SECRET)

        return result

    def apply_difference_type(
        self,
        diff,
        chat_hashes,
    ):
        state = getattr(diff, 'intermediate_state', None) or diff.state
        self.set_state(state, reset=False)

        # diff.other_updates can contain things like UpdateChannelTooLong and UpdateNewChannelMessage.
        # We need to process those as if they were socket updates to discard any we have already handled.
        updates = []
        self.process_updates(tl.Updates(
            updates=diff.other_updates,
            users=diff.users,
            chats=diff.chats,
            date=1,  # anything not-None
            seq=NO_SEQ,  # this way date is not used
        ), chat_hashes, updates)

        updates.extend(tl.UpdateNewMessage(
            message=m,
            pts=NO_SEQ,
            pts_count=NO_SEQ,
        ) for m in diff.new_messages)
        updates.extend(tl.UpdateNewEncryptedMessage(
            message=m,
            qts=NO_SEQ,
        ) for m in diff.new_encrypted_messages)

        return updates, diff.users, diff.chats

    def end_difference(self):
        if __debug__:
            self._trace('Ending account difference')

        account = ENTRY_ACCOUNT in self.getting_diff_for
        secret = ENTRY_SECRET in self.getting_diff_for

        if not account and not secret:
            raise RuntimeError('Should not be ending get difference when neither account or secret was diff was active')

        # Both may be active if both expired at the same time.
        if account:
            self.end_get_diff(ENTRY_ACCOUNT)
        if secret:
            self.end_get_diff(ENTRY_SECRET)

    # endregion Getting and applying account difference.

    # region Getting and applying channel difference.

    # Return the request that needs to be made to get a channel's difference, if any.
    def get_channel_difference(
        self,
        chat_hashes,
    ):
        entry = next((id for id in self.getting_diff_for if isinstance(id, int)), None)
        if not entry:
            return None

        packed = chat_hashes.get(entry)
        if not packed:
            # Cannot get channel difference as we're missing its hash
            # TODO we should probably log this
            self.end_get_diff(entry)
            # Remove the outdated `pts` entry from the map so that the next update can correct
            # it. Otherwise, it will spam that the access hash is missing.
            self.map.pop(entry, None)
            return None

        state = self.map.get(entry)
        if not state:
            raise RuntimeError('Should not try to get difference for an entry without known state')

        gd = fn.updates.GetChannelDifferenceRequest(
            force=False,
            channel=tl.InputChannel(packed.id, packed.hash),
            filter=tl.ChannelMessagesFilterEmpty(),
            pts=state.pts,
            limit=BOT_CHANNEL_DIFF_LIMIT if chat_hashes.self_bot else USER_CHANNEL_DIFF_LIMIT
        )
        if __debug__:
            self._trace('Requesting channel difference %s', gd)
        return gd

    # Similar to [`MessageBox::process_updates`], but using the result from getting difference.
    def apply_channel_difference(
        self,
        request,
        diff,
        chat_hashes,
    ):
        entry = request.channel.channel_id
        if __debug__:
            self._trace('Applying channel difference for %r: %s', entry, diff)

        self.possible_gaps.pop(entry, None)

        if isinstance(diff, tl.updates.ChannelDifferenceEmpty):
            assert diff.final
            self.end_get_diff(entry)
            self.map[entry].pts = diff.pts
            return [], [], []
        elif isinstance(diff, tl.updates.ChannelDifferenceTooLong):
            assert diff.final
            self.map[entry].pts = diff.dialog.pts
            chat_hashes.extend(diff.users, diff.chats)
            self.reset_channel_deadline(entry, diff.timeout)
            # This `diff` has the "latest messages and corresponding chats", but it would
            # be strange to give the user only partial changes of these when they would
            # expect all updates to be fetched. Instead, nothing is returned.
            return [], [], []
        elif isinstance(diff, tl.updates.ChannelDifference):
            if diff.final:
                self.end_get_diff(entry)

            self.map[entry].pts = diff.pts
            chat_hashes.extend(diff.users, diff.chats)

            updates = []
            self.process_updates(tl.Updates(
                updates=diff.other_updates,
                users=diff.users,
                chats=diff.chats,
                date=1,  # anything not-None
                seq=NO_SEQ,  # this way date is not used
            ), chat_hashes, updates)

            updates.extend(tl.UpdateNewChannelMessage(
                message=m,
                pts=NO_SEQ,
                pts_count=NO_SEQ,
            ) for m in diff.new_messages)
            self.reset_channel_deadline(entry, None)

            return updates, diff.users, diff.chats

    def end_channel_difference(self, request, reason: PrematureEndReason, chat_hashes):
        entry = request.channel.channel_id
        if __debug__:
            self._trace('Ending channel difference for %r because %s', entry, reason)

        if reason == PrematureEndReason.TEMPORARY_SERVER_ISSUES:
            # Temporary issues. End getting difference without updating the pts so we can retry later.
            self.possible_gaps.pop(entry, None)
            self.end_get_diff(entry)
        elif reason == PrematureEndReason.BANNED:
            # Banned in the channel. Forget its state since we can no longer fetch updates from it.
            self.possible_gaps.pop(entry, None)
            self.end_get_diff(entry)
            del self.map[entry]
        else:
            raise RuntimeError('Unknown reason to end channel difference')

    # endregion Getting and applying channel difference.
