import asyncio
import inspect
import itertools
import logging
import random
import time

from .users import UserMethods
from .. import events, utils, errors
from ..tl import types, functions

__log__ = logging.getLogger(__name__)


class UpdateMethods(UserMethods):

    # region Public methods

    async def _run_until_disconnected(self):
        try:
            await self.disconnected
        except KeyboardInterrupt:
            await self.disconnect()

    def run_until_disconnected(self):
        """
        Runs the event loop until `disconnect` is called or if an error
        while connecting/sending/receiving occurs in the background. In
        the latter case, said error will ``raise`` so you have a chance
        to ``except`` it on your own code.

        If the loop is already running, this method returns a coroutine
        that you should await on your own code.
        """
        if self.loop.is_running():
            return self._run_until_disconnected()
        try:
            return self.loop.run_until_complete(self.disconnected)
        except KeyboardInterrupt:
            # Importing the magic sync module turns disconnect into sync.
            # TODO Maybe disconnect() should not need the magic module...
            if inspect.iscoroutinefunction(self.disconnect):
                self.loop.run_until_complete(self.disconnect())
            else:
                self.disconnect()

    def on(self, event):
        """
        Decorator helper method around `add_event_handler`. Example:

        >>> from telethon import TelegramClient, events
        >>> client = TelegramClient(...)
        >>>
        >>> @client.on(events.NewMessage)
        ... async def handler(event):
        ...     ...
        ...
        >>>

        Args:
            event (`_EventBuilder` | `type`):
                The event builder class or instance to be used,
                for instance ``events.NewMessage``.
        """
        def decorator(f):
            self.add_event_handler(f, event)
            return f

        return decorator

    def add_event_handler(self, callback, event=None):
        """
        Registers the given callback to be called on the specified event.

        Args:
            callback (`callable`):
                The callable function accepting one parameter to be used.

            event (`_EventBuilder` | `type`, optional):
                The event builder class or instance to be used,
                for instance ``events.NewMessage``.

                If left unspecified, `telethon.events.raw.Raw` (the
                :tl:`Update` objects with no further processing) will
                be passed instead.
        """
        if isinstance(event, type):
            event = event()
        elif not event:
            event = events.Raw()

        self._events_pending_resolve.append(event)
        self._event_builders_count[type(event)] += 1
        self._event_builders.append((event, callback))

    def remove_event_handler(self, callback, event=None):
        """
        Inverse operation of :meth:`add_event_handler`.

        If no event is given, all events for this callback are removed.
        Returns how many callbacks were removed.
        """
        found = 0
        if event and not isinstance(event, type):
            event = type(event)

        i = len(self._event_builders)
        while i:
            i -= 1
            ev, cb = self._event_builders[i]
            if cb == callback and (not event or isinstance(ev, event)):
                type_ev = type(ev)
                self._event_builders_count[type_ev] -= 1
                if not self._event_builders_count[type_ev]:
                    del self._event_builders_count[type_ev]

                del self._event_builders[i]
                found += 1

        return found

    def list_event_handlers(self):
        """
        Lists all added event handlers, returning a list of pairs
        consisting of (callback, event).
        """
        return [(callback, event) for event, callback in self._event_builders]

    async def catch_up(self):
        state = self.session.get_update_state(0)
        if not state or not state.pts:
            return

        self.session.catching_up = True
        try:
            while True:
                d = await self(functions.updates.GetDifferenceRequest(
                    state.pts, state.date, state.qts))
                if isinstance(d, types.updates.DifferenceEmpty):
                    state.date = d.date
                    state.seq = d.seq
                    break
                elif isinstance(d, (types.updates.DifferenceSlice,
                                    types.updates.Difference)):
                    if isinstance(d, types.updates.Difference):
                        state = d.state
                    elif d.intermediate_state.pts > state.pts:
                        state = d.intermediate_state
                    else:
                        # TODO Figure out why other applications can rely on
                        # using always the intermediate_state to eventually
                        # reach a DifferenceEmpty, but that leads to an
                        # infinite loop here (so check against old pts to stop)
                        break

                    self._handle_update(types.Updates(
                        users=d.users,
                        chats=d.chats,
                        date=state.date,
                        seq=state.seq,
                        updates=d.other_updates + [
                            types.UpdateNewMessage(m, 0, 0)
                            for m in d.new_messages
                        ]
                    ))
                elif isinstance(d, types.updates.DifferenceTooLong):
                    break
        finally:
            self.session.set_update_state(0, state)
            self.session.catching_up = False

    # endregion

    # region Private methods

    def _handle_update(self, update):
        self.session.process_entities(update)
        if isinstance(update, (types.Updates, types.UpdatesCombined)):
            entities = {utils.get_peer_id(x): x for x in
                        itertools.chain(update.users, update.chats)}
            for u in update.updates:
                u._entities = entities
                self._handle_update(u)
        elif isinstance(update, types.UpdateShort):
            self._handle_update(update.update)
        else:
            update._entities = getattr(update, '_entities', {})
            if self._updates_queue is None:
                self._loop.create_task(self._dispatch_update(update))
            else:
                self._updates_queue.put_nowait(update)
                if not self._dispatching_updates_queue.is_set():
                    self._dispatching_updates_queue.set()
                    self._loop.create_task(self._dispatch_queue_updates())

        need_diff = False
        if hasattr(update, 'pts') and update.pts is not None:
            if self._state.pts and (update.pts - self._state.pts) > 1:
                need_diff = True
            self._state.pts = update.pts
        if hasattr(update, 'date'):
            self._state.date = update.date
        if hasattr(update, 'seq'):
            self._state.seq = update.seq

        # TODO make use of need_diff

    async def _update_loop(self):
        # Pings' ID don't really need to be secure, just "random"
        rnd = lambda: random.randrange(-2**63, 2**63)
        while self.is_connected():
            try:
                await asyncio.wait_for(
                    self.disconnected, timeout=60, loop=self._loop
                )
                continue  # We actually just want to act upon timeout
            except asyncio.TimeoutError:
                pass
            except asyncio.CancelledError:
                await self.disconnect()
                return
            except Exception as e:
                continue  # Any disconnected exception should be ignored

            # We also don't really care about their result.
            # Just send them periodically.
            self._sender.send(functions.PingRequest(rnd()))

            # Entities and cached files are not saved when they are
            # inserted because this is a rather expensive operation
            # (default's sqlite3 takes ~0.1s to commit changes). Do
            # it every minute instead. No-op if there's nothing new.
            self.session.save()

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

                await self(functions.updates.GetStateRequest())

    async def _dispatch_queue_updates(self):
        while not self._updates_queue.empty():
            await self._dispatch_update(self._updates_queue.get_nowait())

        self._dispatching_updates_queue.clear()

    async def _dispatch_update(self, update):
        if self._events_pending_resolve:
            if self._event_resolve_lock.locked():
                async with self._event_resolve_lock:
                    pass
            else:
                async with self._event_resolve_lock:
                    for event in self._events_pending_resolve:
                        await event.resolve(self)

            self._events_pending_resolve.clear()

        # TODO We can improve this further
        # If we had a way to get all event builders for
        # a type instead looping over them all always.
        built = {builder: builder.build(update)
                 for builder in self._event_builders_count}

        for builder, callback in self._event_builders:
            event = built[type(builder)]
            if not event or not builder.filter(event):
                continue

            if hasattr(event, '_set_client'):
                event._set_client(self)
            else:
                event._client = self

            event.original_update = update
            try:
                await callback(event)
            except events.StopPropagation:
                name = getattr(callback, '__name__', repr(callback))
                __log__.debug(
                    'Event handler "%s" stopped chain of propagation '
                    'for event %s.', name, type(event).__name__
                )
                break
            except Exception:
                name = getattr(callback, '__name__', repr(callback))
                __log__.exception('Unhandled exception on %s', name)

    async def _handle_auto_reconnect(self):
        # Upon reconnection, we want to send getState
        # for Telegram to keep sending us updates.
        try:
            __log__.info('Asking for the current state after reconnect...')
            state = await self(functions.updates.GetStateRequest())
            __log__.info('Got new state! %s', state)
        except errors.RPCError as e:
            __log__.info('Failed to get current state: %r', e)

    # endregion
