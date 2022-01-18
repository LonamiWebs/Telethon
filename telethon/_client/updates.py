import asyncio
import inspect
import itertools
import random
import sys
import time
import traceback
import typing
import logging

from ..errors._rpcbase import RpcError
from .._events.common import EventBuilder, EventCommon
from .._events.raw import Raw
from .._events.base import StopPropagation, _get_handlers
from .._misc import utils
from .. import _tl

if typing.TYPE_CHECKING:
    from .telegramclient import TelegramClient


Callback = typing.Callable[[typing.Any], typing.Any]


async def set_receive_updates(self: 'TelegramClient', receive_updates):
    self._no_updates = not receive_updates
    if receive_updates:
        await self(_tl.fn.updates.GetState())

async def run_until_disconnected(self: 'TelegramClient'):
    # Make a high-level request to notify that we want updates
    await self(_tl.fn.updates.GetState())
    await self._sender.wait_disconnected()

def on(self: 'TelegramClient', event: EventBuilder):
    def decorator(f):
        self.add_event_handler(f, event)
        return f

    return decorator

def add_event_handler(
        self: 'TelegramClient',
        callback: Callback,
        event: EventBuilder = None):
    builders = _get_handlers(callback)
    if builders is not None:
        for event in builders:
            self._event_builders.append((event, callback))
        return

    if isinstance(event, type):
        event = event()
    elif not event:
        event = Raw()

    self._event_builders.append((event, callback))

def remove_event_handler(
        self: 'TelegramClient',
        callback: Callback,
        event: EventBuilder = None) -> int:
    found = 0
    if event and not isinstance(event, type):
        event = type(event)

    i = len(self._event_builders)
    while i:
        i -= 1
        ev, cb = self._event_builders[i]
        if cb == callback and (not event or isinstance(ev, event)):
            del self._event_builders[i]
            found += 1

    return found

def list_event_handlers(self: 'TelegramClient')\
        -> 'typing.Sequence[typing.Tuple[Callback, EventBuilder]]':
    return [(callback, event) for event, callback in self._event_builders]

async def catch_up(self: 'TelegramClient'):
    return
    self._catching_up = True
    try:
        while True:
            d = await self(_tl.fn.updates.GetDifference(
                pts, date, 0
            ))
            if isinstance(d, (_tl.updates.DifferenceSlice,
                                _tl.updates.Difference)):
                if isinstance(d, _tl.updates.Difference):
                    state = d.state
                else:
                    state = d.intermediate_state

                pts, date = state.pts, state.date
                _handle_update(self, _tl.Updates(
                    users=d.users,
                    chats=d.chats,
                    date=state.date,
                    seq=state.seq,
                    updates=d.other_updates + [
                        _tl.UpdateNewMessage(m, 0, 0)
                        for m in d.new_messages
                    ]
                ))

                # TODO Implement upper limit (max_pts)
                # We don't want to fetch updates we already know about.
                #
                # We may still get duplicates because the Difference
                # contains a lot of updates and presumably only has
                # the state for the last one, but at least we don't
                # unnecessarily fetch too many.
                #
                # updates.getDifference's pts_total_limit seems to mean
                # "how many pts is the request allowed to return", and
                # if there is more than that, it returns "too long" (so
                # there would be duplicate updates since we know about
                # some). This can be used to detect collisions (i.e.
                # it would return an update we have already seen).
            else:
                if isinstance(d, _tl.updates.DifferenceEmpty):
                    date = d.date
                elif isinstance(d, _tl.updates.DifferenceTooLong):
                    pts = d.pts
                break
    except (ConnectionError, asyncio.CancelledError):
        pass
    finally:
        self._catching_up = False


# It is important to not make _handle_update async because we rely on
# the order that the updates arrive in to update the pts and date to
# be always-increasing. There is also no need to make this async.
def _handle_update(self: 'TelegramClient', update):
    if isinstance(update, (_tl.Updates, _tl.UpdatesCombined)):
        entities = {utils.get_peer_id(x): x for x in
                    itertools.chain(update.users, update.chats)}
        for u in update.updates:
            _process_update(self, u, entities, update.updates)
    elif isinstance(update, _tl.UpdateShort):
        _process_update(self, update.update, {}, None)
    else:
        _process_update(self, update, {}, None)


def _process_update(self: 'TelegramClient', update, entities, others):
    # This part is somewhat hot so we don't bother patching
    # update with channel ID/its state. Instead we just pass
    # arguments which is faster.
    args = (update, entities, others, channel_id, None)
    if self._dispatching_updates_queue is None:
        task = asyncio.create_task(_dispatch_update(self, *args))
        self._updates_queue.add(task)
        task.add_done_callback(lambda _: self._updates_queue.discard(task))
    else:
        self._updates_queue.put_nowait(args)
        if not self._dispatching_updates_queue.is_set():
            self._dispatching_updates_queue.set()
            asyncio.create_task(_dispatch_queue_updates(self))

async def _update_loop(self: 'TelegramClient'):
    # Pings' ID don't really need to be secure, just "random"
    rnd = lambda: random.randrange(-2**63, 2**63)
    while self.is_connected():
        try:
            await asyncio.wait_for(self.run_until_disconnected(), timeout=60)
            continue  # We actually just want to act upon timeout
        except asyncio.TimeoutError:
            pass
        except asyncio.CancelledError:
            return
        except Exception as e:
            # Any disconnected exception should be ignored (or it may hint at
            # another problem, leading to an infinite loop, hence the logging call)
            self._log[__name__].info('Exception waiting on a disconnect: %s', e)
            continue

        # Check if we have any exported senders to clean-up periodically
        await self._clean_exported_senders()

        # Don't bother sending pings until the low-level connection is
        # ready, otherwise a lot of pings will be batched to be sent upon
        # reconnect, when we really don't care about that.
        if not self._sender._transport_connected():
            continue

        # We also don't really care about their result.
        # Just send them periodically.
        try:
            self._sender._keepalive_ping(rnd())
        except (ConnectionError, asyncio.CancelledError):
            return

        # Entities are not saved when they are inserted because this is a rather expensive
        # operation (default's sqlite3 takes ~0.1s to commit changes). Do it every minute
        # instead. No-op if there's nothing new.
        await self._session.save()

        # We need to send some content-related request at least hourly
        # for Telegram to keep delivering updates, otherwise they will
        # just stop even if we're connected. Do so every 30 minutes.
        #
        # TODO Call getDifference instead since it's more relevant
        if time.time() - self._last_request > 30 * 60:
            if not await self.is_user_authorized():
                # What can be the user doing for so
                # long without being logged in...?
                continue

            try:
                await self(_tl.fn.updates.GetState())
            except (ConnectionError, asyncio.CancelledError):
                return

async def _dispatch_queue_updates(self: 'TelegramClient'):
    while not self._updates_queue.empty():
        await _dispatch_update(self, *self._updates_queue.get_nowait())

    self._dispatching_updates_queue.clear()

async def _dispatch_update(self: 'TelegramClient', update, entities, others, channel_id, pts_date):
    built = EventBuilderDict(self, update, entities, others)

    for builder, callback in self._event_builders:
        event = built[type(builder)]
        if not event:
            continue

        if not builder.resolved:
            await builder.resolve(self)

        filter = builder.filter(event)
        if inspect.isawaitable(filter):
            filter = await filter
        if not filter:
            continue

        try:
            await callback(event)
        except StopPropagation:
            name = getattr(callback, '__name__', repr(callback))
            self._log[__name__].debug(
                'Event handler "%s" stopped chain of propagation '
                'for event %s.', name, type(event).__name__
            )
            break
        except Exception as e:
            if not isinstance(e, asyncio.CancelledError) or self.is_connected():
                name = getattr(callback, '__name__', repr(callback))
                self._log[__name__].exception('Unhandled exception on %s', name)

async def _dispatch_event(self: 'TelegramClient', event):
    """
    Dispatches a single, out-of-order event. Used by `AlbumHack`.
    """
    # We're duplicating a most logic from `_dispatch_update`, but all in
    # the name of speed; we don't want to make it worse for all updates
    # just because albums may need it.
    for builder, callback in self._event_builders:
        if isinstance(builder, Raw):
            continue
        if not isinstance(event, builder.Event):
            continue

        if not builder.resolved:
            await builder.resolve(self)

        filter = builder.filter(event)
        if inspect.isawaitable(filter):
            filter = await filter
        if not filter:
            continue

        try:
            await callback(event)
        except StopPropagation:
            name = getattr(callback, '__name__', repr(callback))
            self._log[__name__].debug(
                'Event handler "%s" stopped chain of propagation '
                'for event %s.', name, type(event).__name__
            )
            break
        except Exception as e:
            if not isinstance(e, asyncio.CancelledError) or self.is_connected():
                name = getattr(callback, '__name__', repr(callback))
                self._log[__name__].exception('Unhandled exception on %s', name)

async def _get_difference(self: 'TelegramClient', update, entities, channel_id, pts_date):
    """
    Get the difference for this `channel_id` if any, then load entities.

    Calls :tl:`updates.getDifference`, which fills the entities cache
    (always done by `__call__`) and lets us know about the full entities.
    """
    # Fetch since the last known pts/date before this update arrived,
    # in order to fetch this update at full, including its entities.
    self._log[__name__].debug('Getting difference for entities '
                                'for %r', update.__class__)
    if channel_id:
        # There are reports where we somehow call get channel difference
        # with `InputPeerEmpty`. Check our assumptions to better debug
        # this when it happens.
        assert isinstance(channel_id, int), 'channel_id was {}, not int in {}'.format(type(channel_id), update)
        try:
            # Wrap the ID inside a peer to ensure we get a channel back.
            where = await self.get_input_entity(_tl.PeerChannel(channel_id))
        except ValueError:
            # There's a high chance that this fails, since
            # we are getting the difference to fetch entities.
            return

        if not pts_date:
            # First-time, can't get difference. Get pts instead.
            result = await self(_tl.fn.channels.GetFullChannel(
                utils.get_input_channel(where)
            ))
            return

        result = await self(_tl.fn.updates.GetChannelDifference(
            channel=where,
            filter=_tl.ChannelMessagesFilterEmpty(),
            pts=pts_date,  # just pts
            limit=100,
            force=True
        ))
    else:
        if not pts_date[0]:
            # First-time, can't get difference. Get pts instead.
            result = await self(_tl.fn.updates.GetState())
            return

        result = await self(_tl.fn.updates.GetDifference(
            pts=pts_date[0],
            date=pts_date[1],
            qts=0
        ))

    if isinstance(result, (_tl.updates.Difference,
                            _tl.updates.DifferenceSlice,
                            _tl.updates.ChannelDifference,
                            _tl.updates.ChannelDifferenceTooLong)):
        entities.update({
            utils.get_peer_id(x): x for x in
            itertools.chain(result.users, result.chats)
        })

async def _handle_auto_reconnect(self: 'TelegramClient'):
    # TODO Catch-up
    # For now we make a high-level request to let Telegram
    # know we are still interested in receiving more updates.
    try:
        await self.get_me()
    except Exception as e:
        self._log[__name__].warning('Error executing high-level request '
                                    'after reconnect: %s: %s', type(e), e)

    return
    try:
        self._log[__name__].info(
            'Asking for the current state after reconnect...')

        # TODO consider:
        # If there aren't many updates while the client is disconnected
        # (I tried with up to 20), Telegram seems to send them without
        # asking for them (via updates.getDifference).
        #
        # On disconnection, the library should probably set a "need
        # difference" or "catching up" flag so that any new updates are
        # ignored, and then the library should call updates.getDifference
        # itself to fetch them.
        #
        # In any case (either there are too many updates and Telegram
        # didn't send them, or there isn't a lot and Telegram sent them
        # but we dropped them), we fetch the new difference to get all
        # missed updates. I feel like this would be the best solution.

        # If a disconnection occurs, the old known state will be
        # the latest one we were aware of, so we can catch up since
        # the most recent state we were aware of.
        await self.catch_up()

        self._log[__name__].info('Successfully fetched missed updates')
    except RpcError as e:
        self._log[__name__].warning('Failed to get missed updates after '
                                    'reconnect: %r', e)
    except Exception:
        self._log[__name__].exception(
            'Unhandled exception while getting update difference after reconnect')


class EventBuilderDict:
    """
    Helper "dictionary" to return events from types and cache them.
    """
    def __init__(self, client: 'TelegramClient', update, entities, others):
        self.client = client
        self.update = update
        self.entities = entities
        self.others = others

    def __getitem__(self, builder):
        try:
            return self.__dict__[builder]
        except KeyError:
            event = self.__dict__[builder] = builder.build(
                self.update, self.others, self.client._session_state.user_id, self.entities or {}, self.client)

            if isinstance(event, EventCommon):
                # TODO eww
                event.original_update = self.update
                event._entities = self.entities or {}
                event._set_client(self.client)

            return event
