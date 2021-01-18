import asyncio
import inspect
import itertools
import random
import time
import typing

from .. import events, utils, errors
from ..events.common import EventBuilder, EventCommon
from ..tl import types, functions

if typing.TYPE_CHECKING:
    from .telegramclient import TelegramClient


class UpdateMethods:

    # region Public methods

    async def _run_until_disconnected(self: 'TelegramClient'):
        try:
            # Make a high-level request to notify that we want updates
            await self(functions.updates.GetStateRequest())
            return await self.disconnected
        except KeyboardInterrupt:
            pass
        finally:
            await self.disconnect()

    def run_until_disconnected(self: 'TelegramClient'):
        """
        Runs the event loop until the library is disconnected.

        It also notifies Telegram that we want to receive updates
        as described in https://core.telegram.org/api/updates.

        Manual disconnections can be made by calling `disconnect()
        <telethon.client.telegrambaseclient.TelegramBaseClient.disconnect>`
        or sending a ``KeyboardInterrupt`` (e.g. by pressing ``Ctrl+C`` on
        the console window running the script).

        If a disconnection error occurs (i.e. the library fails to reconnect
        automatically), said error will be raised through here, so you have a
        chance to ``except`` it on your own code.

        If the loop is already running, this method returns a coroutine
        that you should await on your own code.

        .. note::

            If you want to handle ``KeyboardInterrupt`` in your code,
            simply run the event loop in your code too in any way, such as
            ``loop.run_forever()`` or ``await client.disconnected`` (e.g.
            ``loop.run_until_complete(client.disconnected)``).

        Example
            .. code-block:: python

                # Blocks the current task here until a disconnection occurs.
                #
                # You will still receive updates, since this prevents the
                # script from exiting.
                await client.run_until_disconnected()
        """
        if self.loop.is_running():
            return self._run_until_disconnected()
        try:
            return self.loop.run_until_complete(self._run_until_disconnected())
        except KeyboardInterrupt:
            pass
        finally:
            # No loop.run_until_complete; it's already syncified
            self.disconnect()

    def on(self: 'TelegramClient', event: EventBuilder):
        """
        Decorator used to `add_event_handler` more conveniently.


        Arguments
            event (`_EventBuilder` | `type`):
                The event builder class or instance to be used,
                for instance ``events.NewMessage``.

        Example
            .. code-block:: python

                from telethon import TelegramClient, events
                client = TelegramClient(...)

                # Here we use client.on
                @client.on(events.NewMessage)
                async def handler(event):
                    ...
        """
        def decorator(f):
            self.add_event_handler(f, event)
            return f

        return decorator

    def add_event_handler(
            self: 'TelegramClient',
            callback: callable,
            event: EventBuilder = None):
        """
        Registers a new event handler callback.

        The callback will be called when the specified event occurs.

        Arguments
            callback (`callable`):
                The callable function accepting one parameter to be used.

                Note that if you have used `telethon.events.register` in
                the callback, ``event`` will be ignored, and instead the
                events you previously registered will be used.

            event (`_EventBuilder` | `type`, optional):
                The event builder class or instance to be used,
                for instance ``events.NewMessage``.

                If left unspecified, `telethon.events.raw.Raw` (the
                :tl:`Update` objects with no further processing) will
                be passed instead.

        Example
            .. code-block:: python

                from telethon import TelegramClient, events
                client = TelegramClient(...)

                async def handler(event):
                    ...

                client.add_event_handler(handler, events.NewMessage)
        """
        builders = events._get_handlers(callback)
        if builders is not None:
            for event in builders:
                self._event_builders.append((event, callback))
            return

        if isinstance(event, type):
            event = event()
        elif not event:
            event = events.Raw()

        self._event_builders.append((event, callback))

    def remove_event_handler(
            self: 'TelegramClient',
            callback: callable,
            event: EventBuilder = None) -> int:
        """
        Inverse operation of `add_event_handler()`.

        If no event is given, all events for this callback are removed.
        Returns how many callbacks were removed.

        Example
            .. code-block:: python

                @client.on(events.Raw)
                @client.on(events.NewMessage)
                async def handler(event):
                    ...

                # Removes only the "Raw" handling
                # "handler" will still receive "events.NewMessage"
                client.remove_event_handler(handler, events.Raw)

                # "handler" will stop receiving anything
                client.remove_event_handler(handler)
        """
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
            -> 'typing.Sequence[typing.Tuple[callable, EventBuilder]]':
        """
        Lists all registered event handlers.

        Returns
            A list of pairs consisting of ``(callback, event)``.

        Example
            .. code-block:: python

                @client.on(events.NewMessage(pattern='hello'))
                async def on_greeting(event):
                    '''Greets someone'''
                    await event.reply('Hi')

                for callback, event in client.list_event_handlers():
                    print(id(callback), type(event))
        """
        return [(callback, event) for event, callback in self._event_builders]

    async def catch_up(self: 'TelegramClient'):
        """
        "Catches up" on the missed updates while the client was offline.
        You should call this method after registering the event handlers
        so that the updates it loads can by processed by your script.

        This can also be used to forcibly fetch new updates if there are any.

        Example
            .. code-block:: python

                await client.catch_up()
        """
        pts, date = self._state_cache[None]
        if not pts:
            return

        self.session.catching_up = True
        try:
            while True:
                d = await self(functions.updates.GetDifferenceRequest(
                    pts, date, 0
                ))
                if isinstance(d, (types.updates.DifferenceSlice,
                                  types.updates.Difference)):
                    if isinstance(d, types.updates.Difference):
                        state = d.state
                    else:
                        state = d.intermediate_state

                    pts, date = state.pts, state.date
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
                    if isinstance(d, types.updates.DifferenceEmpty):
                        date = d.date
                    elif isinstance(d, types.updates.DifferenceTooLong):
                        pts = d.pts
                    break
        except (ConnectionError, asyncio.CancelledError):
            pass
        finally:
            # TODO Save new pts to session
            self._state_cache._pts_date = (pts, date)
            self.session.catching_up = False

    # endregion

    # region Private methods

    # It is important to not make _handle_update async because we rely on
    # the order that the updates arrive in to update the pts and date to
    # be always-increasing. There is also no need to make this async.
    def _handle_update(self: 'TelegramClient', update):
        self.session.process_entities(update)
        self._entity_cache.add(update)

        if isinstance(update, (types.Updates, types.UpdatesCombined)):
            entities = {utils.get_peer_id(x): x for x in
                        itertools.chain(update.users, update.chats)}
            for u in update.updates:
                self._process_update(u, update.updates, entities=entities)
        elif isinstance(update, types.UpdateShort):
            self._process_update(update.update, None)
        else:
            self._process_update(update, None)

        self._state_cache.update(update)

    def _process_update(self: 'TelegramClient', update, others, entities=None):
        update._entities = entities or {}

        # This part is somewhat hot so we don't bother patching
        # update with channel ID/its state. Instead we just pass
        # arguments which is faster.
        channel_id = self._state_cache.get_channel_id(update)
        args = (update, others, channel_id, self._state_cache[channel_id])
        if self._dispatching_updates_queue is None:
            task = self.loop.create_task(self._dispatch_update(*args))
            self._updates_queue.add(task)
            task.add_done_callback(lambda _: self._updates_queue.discard(task))
        else:
            self._updates_queue.put_nowait(args)
            if not self._dispatching_updates_queue.is_set():
                self._dispatching_updates_queue.set()
                self.loop.create_task(self._dispatch_queue_updates())

        self._state_cache.update(update)

    async def _update_loop(self: 'TelegramClient'):
        # Pings' ID don't really need to be secure, just "random"
        rnd = lambda: random.randrange(-2**63, 2**63)
        while self.is_connected():
            try:
                await asyncio.wait_for(
                    self.disconnected, timeout=60
                )
                continue  # We actually just want to act upon timeout
            except asyncio.TimeoutError:
                pass
            except asyncio.CancelledError:
                return
            except Exception:
                continue  # Any disconnected exception should be ignored

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

                try:
                    await self(functions.updates.GetStateRequest())
                except (ConnectionError, asyncio.CancelledError):
                    return

    async def _dispatch_queue_updates(self: 'TelegramClient'):
        while not self._updates_queue.empty():
            await self._dispatch_update(*self._updates_queue.get_nowait())

        self._dispatching_updates_queue.clear()

    async def _dispatch_update(self: 'TelegramClient', update, others, channel_id, pts_date):
        if not self._entity_cache.ensure_cached(update):
            # We could add a lock to not fetch the same pts twice if we are
            # already fetching it. However this does not happen in practice,
            # which makes sense, because different updates have different pts.
            if self._state_cache.update(update, check_only=True):
                # If the update doesn't have pts, fetching won't do anything.
                # For example, UpdateUserStatus or UpdateChatUserTyping.
                try:
                    await self._get_difference(update, channel_id, pts_date)
                except OSError:
                    pass  # We were disconnected, that's okay
                except errors.RPCError:
                    # There's a high chance the request fails because we lack
                    # the channel. Because these "happen sporadically" (#1428)
                    # we should be okay (no flood waits) even if more occur.
                    pass
                except ValueError:
                    # There is a chance that GetFullChannelRequest and GetDifferenceRequest
                    # inside the _get_difference() function will end up with
                    # ValueError("Request was unsuccessful N time(s)") for whatever reasons.
                    pass

        if not self._self_input_peer:
            # Some updates require our own ID, so we must make sure
            # that the event builder has offline access to it. Calling
            # `get_me()` will cache it under `self._self_input_peer`.
            #
            # It will return `None` if we haven't logged in yet which is
            # fine, we will just retry next time anyway.
            try:
                await self.get_me(input_peer=True)
            except OSError:
                pass  # might not have connection

        built = EventBuilderDict(self, update, others)
        for conv_set in self._conversations.values():
            for conv in conv_set:
                ev = built[events.NewMessage]
                if ev:
                    conv._on_new_message(ev)

                ev = built[events.MessageEdited]
                if ev:
                    conv._on_edit(ev)

                ev = built[events.MessageRead]
                if ev:
                    conv._on_read(ev)

                if conv._custom:
                    await conv._check_custom(built)

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
            except errors.AlreadyInConversationError:
                name = getattr(callback, '__name__', repr(callback))
                self._log[__name__].debug(
                    'Event handler "%s" already has an open conversation, '
                    'ignoring new one', name)
            except events.StopPropagation:
                name = getattr(callback, '__name__', repr(callback))
                self._log[__name__].debug(
                    'Event handler "%s" stopped chain of propagation '
                    'for event %s.', name, type(event).__name__
                )
                break
            except Exception as e:
                if not isinstance(e, asyncio.CancelledError) or self.is_connected():
                    name = getattr(callback, '__name__', repr(callback))
                    self._log[__name__].exception('Unhandled exception on %s',
                                                  name)

    async def _dispatch_event(self: 'TelegramClient', event):
        """
        Dispatches a single, out-of-order event. Used by `AlbumHack`.
        """
        # We're duplicating a most logic from `_dispatch_update`, but all in
        # the name of speed; we don't want to make it worse for all updates
        # just because albums may need it.
        for builder, callback in self._event_builders:
            if isinstance(builder, events.Raw):
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
            except errors.AlreadyInConversationError:
                name = getattr(callback, '__name__', repr(callback))
                self._log[__name__].debug(
                    'Event handler "%s" already has an open conversation, '
                    'ignoring new one', name)
            except events.StopPropagation:
                name = getattr(callback, '__name__', repr(callback))
                self._log[__name__].debug(
                    'Event handler "%s" stopped chain of propagation '
                    'for event %s.', name, type(event).__name__
                )
                break
            except Exception as e:
                if not isinstance(e, asyncio.CancelledError) or self.is_connected():
                    name = getattr(callback, '__name__', repr(callback))
                    self._log[__name__].exception('Unhandled exception on %s',
                                                  name)

    async def _get_difference(self: 'TelegramClient', update, channel_id, pts_date):
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
                where = await self.get_input_entity(types.PeerChannel(channel_id))
            except ValueError:
                # There's a high chance that this fails, since
                # we are getting the difference to fetch entities.
                return

            if not pts_date:
                # First-time, can't get difference. Get pts instead.
                result = await self(functions.channels.GetFullChannelRequest(
                    utils.get_input_channel(where)
                ))
                self._state_cache[channel_id] = result.full_chat.pts
                return

            result = await self(functions.updates.GetChannelDifferenceRequest(
                channel=where,
                filter=types.ChannelMessagesFilterEmpty(),
                pts=pts_date,  # just pts
                limit=100,
                force=True
            ))
        else:
            if not pts_date[0]:
                # First-time, can't get difference. Get pts instead.
                result = await self(functions.updates.GetStateRequest())
                self._state_cache[None] = result.pts, result.date
                return

            result = await self(functions.updates.GetDifferenceRequest(
                pts=pts_date[0],
                date=pts_date[1],
                qts=0
            ))

        if isinstance(result, (types.updates.Difference,
                               types.updates.DifferenceSlice,
                               types.updates.ChannelDifference,
                               types.updates.ChannelDifferenceTooLong)):
            update._entities.update({
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
        except errors.RPCError as e:
            self._log[__name__].warning('Failed to get missed updates after '
                                        'reconnect: %r', e)
        except Exception:
            self._log[__name__].exception('Unhandled exception while getting '
                                          'update difference after reconnect')

    # endregion


class EventBuilderDict:
    """
    Helper "dictionary" to return events from types and cache them.
    """
    def __init__(self, client: 'TelegramClient', update, others):
        self.client = client
        self.update = update
        self.others = others

    def __getitem__(self, builder):
        try:
            return self.__dict__[builder]
        except KeyError:
            event = self.__dict__[builder] = builder.build(
                self.update, self.others, self.client._self_id)

            if isinstance(event, EventCommon):
                event.original_update = self.update
                event._entities = self.update._entities
                event._set_client(self.client)
            elif event:
                event._client = self.client

            return event
