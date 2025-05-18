import asyncio
import inspect
import itertools
import random
import sys
import time
import traceback
import typing
import logging
import warnings
from collections import deque
import sqlite3

from .. import events, utils, errors
from ..events.common import EventBuilder, EventCommon
from ..tl import types, functions
from .._updates import GapError, PrematureEndReason
from ..helpers import get_running_loop
from ..version import __version__


if typing.TYPE_CHECKING:
    from .telegramclient import TelegramClient


Callback = typing.Callable[[typing.Any], typing.Any]

class UpdateMethods:

    # region Public methods

    async def _run_until_disconnected(self: 'TelegramClient'):
        try:
            # Make a high-level request to notify that we want updates
            await self(functions.updates.GetStateRequest())
            result = await self.disconnected
            if self._updates_error is not None:
                raise self._updates_error
            return result
        except KeyboardInterrupt:
            pass
        finally:
            await self.disconnect()

    async def set_receive_updates(self: 'TelegramClient', receive_updates):
        """
        Change the value of `receive_updates`.

        This is an `async` method, because in order for Telegram to start
        sending updates again, a request must be made.
        """
        self._no_updates = not receive_updates
        if receive_updates:
            await self(functions.updates.GetStateRequest())

    def run_until_disconnected(self: 'TelegramClient'):
        """
        Runs the event loop until the library is disconnected.

        It also notifies Telegram that we want to receive updates
        as described in https://core.telegram.org/api/updates.
        If an unexpected error occurs during update handling,
        the client will disconnect and said error will be raised.

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
            callback: Callback,
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
            callback: Callback,
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
            -> 'typing.Sequence[typing.Tuple[Callback, EventBuilder]]':
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
        await self._updates_queue.put(types.UpdatesTooLong())

    # endregion

    # region Private methods

    async def _update_loop(self: 'TelegramClient'):
        # If the MessageBox is not empty, the account had to be logged-in to fill in its state.
        # This flag is used to propagate the "you got logged-out" error up (but getting logged-out
        # can only happen if it was once logged-in).
        was_once_logged_in = self._authorized is True or not self._message_box.is_empty()

        self._updates_error = None
        try:
            if self._catch_up:
                # User wants to catch up as soon as the client is up and running,
                # so this is the best place to do it.
                await self.catch_up()

            updates_to_dispatch = deque()

            while self.is_connected():
                if updates_to_dispatch:
                    if self._sequential_updates:
                        await self._dispatch_update(updates_to_dispatch.popleft())
                    else:
                        while updates_to_dispatch:
                            # TODO if _dispatch_update fails for whatever reason, it's not logged! this should be fixed
                            task = self.loop.create_task(self._dispatch_update(updates_to_dispatch.popleft()))
                            self._event_handler_tasks.add(task)
                            task.add_done_callback(self._event_handler_tasks.discard)

                    continue

                if len(self._mb_entity_cache) >= self._entity_cache_limit:
                    self._log[__name__].info(
                        'In-memory entity cache limit reached (%s/%s), flushing to session',
                        len(self._mb_entity_cache),
                        self._entity_cache_limit
                    )
                    self._save_states_and_entities()
                    self._mb_entity_cache.retain(lambda id: id == self._mb_entity_cache.self_id or id in self._message_box.map)
                    if len(self._mb_entity_cache) >= self._entity_cache_limit:
                        warnings.warn('in-memory entities exceed entity_cache_limit after flushing; consider setting a larger limit')

                    self._log[__name__].info(
                        'In-memory entity cache at %s/%s after flushing to session',
                        len(self._mb_entity_cache),
                        self._entity_cache_limit
                    )


                get_diff = self._message_box.get_difference()
                if get_diff:
                    self._log[__name__].debug('Getting difference for account updates')
                    try:
                        diff = await self(get_diff)
                    except (
                        errors.ServerError,
                        errors.TimedOutError,
                        errors.FloodWaitError,
                        ValueError
                    ) as e:
                        # Telegram is having issues
                        self._log[__name__].info('Cannot get difference since Telegram is having issues: %s', type(e).__name__)
                        self._message_box.end_difference()
                        continue
                    except (errors.UnauthorizedError, errors.AuthKeyError) as e:
                        # Not logged in or broken authorization key, can't get difference
                        self._log[__name__].info('Cannot get difference since the account is not logged in: %s', type(e).__name__)
                        self._message_box.end_difference()
                        if was_once_logged_in:
                            self._updates_error = e
                            await self.disconnect()
                            break
                        continue
                    except (errors.TypeNotFoundError, sqlite3.OperationalError) as e:
                        # User is likely doing weird things with their account or session and Telegram gets confused as to what layer they use
                        self._log[__name__].warning('Cannot get difference since the account is likely misusing the session: %s', e)
                        self._message_box.end_difference()
                        self._updates_error = e
                        await self.disconnect()
                        break
                    except OSError as e:
                        # Network is likely down, but it's unclear for how long.
                        # If disconnect is called this task will be cancelled along with the sleep.
                        # If disconnect is not called, getting difference should be retried after a few seconds.
                        self._log[__name__].info('Cannot get difference since the network is down: %s: %s', type(e).__name__, e)
                        await asyncio.sleep(5)
                        continue
                    updates, users, chats = self._message_box.apply_difference(diff, self._mb_entity_cache)
                    if updates:
                        self._log[__name__].info('Got difference for account updates')

                    updates_to_dispatch.extend(self._preprocess_updates(updates, users, chats))
                    continue

                get_diff = self._message_box.get_channel_difference(self._mb_entity_cache)
                if get_diff:
                    self._log[__name__].debug('Getting difference for channel %s updates', get_diff.channel.channel_id)
                    try:
                        diff = await self(get_diff)
                    except (errors.UnauthorizedError, errors.AuthKeyError) as e:
                        # Not logged in or broken authorization key, can't get difference
                        self._log[__name__].warning(
                            'Cannot get difference for channel %s since the account is not logged in: %s',
                            get_diff.channel.channel_id, type(e).__name__
                        )
                        self._message_box.end_channel_difference(
                            get_diff,
                            PrematureEndReason.TEMPORARY_SERVER_ISSUES,
                            self._mb_entity_cache
                        )
                        if was_once_logged_in:
                            self._updates_error = e
                            await self.disconnect()
                            break
                        continue
                    except (errors.TypeNotFoundError, sqlite3.OperationalError) as e:
                        self._log[__name__].warning(
                            'Cannot get difference for channel %s since the account is likely misusing the session: %s',
                            get_diff.channel.channel_id, e
                        )
                        self._message_box.end_channel_difference(
                            get_diff,
                            PrematureEndReason.TEMPORARY_SERVER_ISSUES,
                            self._mb_entity_cache
                        )
                        self._updates_error = e
                        await self.disconnect()
                        break
                    except (
                        errors.PersistentTimestampOutdatedError,
                        errors.PersistentTimestampInvalidError,
                        errors.ServerError,
                        errors.TimedOutError,
                        errors.FloodWaitError,
                        ValueError
                    ) as e:
                        # According to Telegram's docs:
                        # "Channel internal replication issues, try again later (treat this like an RPC_CALL_FAIL)."
                        # We can treat this as "empty difference" and not update the local pts.
                        # Then this same call will be retried when another gap is detected or timeout expires.
                        #
                        # Another option would be to literally treat this like an RPC_CALL_FAIL and retry after a few
                        # seconds, but if Telegram is having issues it's probably best to wait for it to send another
                        # update (hinting it may be okay now) and retry then.
                        #
                        # This is a bit hacky because MessageBox doesn't really have a way to "not update" the pts.
                        # Instead we manually extract the previously-known pts and use that.
                        #
                        # For PersistentTimestampInvalidError:
                        # Somehow our pts is either too new or the server does not know about this.
                        # We treat this as PersistentTimestampOutdatedError for now.
                        # TODO investigate why/when this happens and if this is the proper solution
                        self._log[__name__].warning(
                            'Getting difference for channel updates %s caused %s;'
                            ' ending getting difference prematurely until server issues are resolved',
                            get_diff.channel.channel_id, type(e).__name__
                        )
                        self._message_box.end_channel_difference(
                            get_diff,
                            PrematureEndReason.TEMPORARY_SERVER_ISSUES,
                            self._mb_entity_cache
                        )
                        continue
                    except (errors.ChannelPrivateError, errors.ChannelInvalidError):
                        # Timeout triggered a get difference, but we have been banned in the channel since then.
                        # Because we can no longer fetch updates from this channel, we should stop keeping track
                        # of it entirely.
                        self._log[__name__].info(
                            'Account is now banned in %d so we can no longer fetch updates from it',
                            get_diff.channel.channel_id
                        )
                        self._message_box.end_channel_difference(
                            get_diff,
                            PrematureEndReason.BANNED,
                            self._mb_entity_cache
                        )
                        continue
                    except OSError as e:
                        self._log[__name__].info(
                            'Cannot get difference for channel %d since the network is down: %s: %s',
                            get_diff.channel.channel_id, type(e).__name__, e
                        )
                        await asyncio.sleep(5)
                        continue

                    updates, users, chats = self._message_box.apply_channel_difference(get_diff, diff, self._mb_entity_cache)
                    if updates:
                        self._log[__name__].info('Got difference for channel %d updates', get_diff.channel.channel_id)

                    updates_to_dispatch.extend(self._preprocess_updates(updates, users, chats))
                    continue

                deadline = self._message_box.check_deadlines()
                deadline_delay = deadline - get_running_loop().time()
                if deadline_delay > 0:
                    # Don't bother sleeping and timing out if the delay is already 0 (pollutes the logs).
                    try:
                        updates = await asyncio.wait_for(self._updates_queue.get(), deadline_delay)
                    except asyncio.TimeoutError:
                        self._log[__name__].debug('Timeout waiting for updates expired')
                        continue
                else:
                    continue

                processed = []
                try:
                    users, chats = self._message_box.process_updates(updates, self._mb_entity_cache, processed)
                except GapError:
                    continue  # get(_channel)_difference will start returning requests

                updates_to_dispatch.extend(self._preprocess_updates(processed, users, chats))
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self._log[__name__].exception(f'Fatal error handling updates (this is a bug in Telethon v{__version__}, please report it)')
            self._updates_error = e
            await self.disconnect()

    def _preprocess_updates(self, updates, users, chats):
        self._mb_entity_cache.extend(users, chats)
        self.session.process_entities(types.contacts.ResolvedPeer(None, users, chats))
        entities = {utils.get_peer_id(x): x
                    for x in itertools.chain(users, chats)}
        for u in updates:
            u._entities = entities
        return updates

    async def _keepalive_loop(self: 'TelegramClient'):
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
            self._save_states_and_entities()

            self.session.save()

    async def _dispatch_update(self: 'TelegramClient', update):
        # TODO only used for AlbumHack, and MessageBox is not really designed for this
        others = None

        if not self._mb_entity_cache.self_id:
            # Some updates require our own ID, so we must make sure
            # that the event builder has offline access to it. Calling
            # `get_me()` will cache it under `self._mb_entity_cache`.
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
                    self._log[__name__].exception('Unhandled exception on %s', name)

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
                    self._log[__name__].exception('Unhandled exception on %s', name)

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
            self._log[__name__].exception(
                'Unhandled exception while getting update difference after reconnect')

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
