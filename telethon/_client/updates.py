import asyncio
import inspect
import itertools
import random
import sys
import time
import traceback
import typing
import logging
import inspect
import bisect
import warnings
from collections import deque

from ..errors._rpcbase import RpcError
from .._events.raw import Raw
from .._events.base import StopPropagation, EventBuilder, EventHandler
from .._events.filters import make_filter, NotResolved
from .._misc import utils
from .. import _tl
from ..types._custom import User, Chat

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

def on(self: 'TelegramClient', *events, priority=0, **filters):
    def decorator(f):
        for event in events:
            self.add_event_handler(f, event, priority=priority, **filters)
        return f

    return decorator

def add_event_handler(
        self: 'TelegramClient',
        callback=None,
        event=None,
        priority=0,
        **filters
):
    if callback is None:
        return functools.partial(add_event_handler, self, event=event, priority=priority, **filters)

    if event is None:
        for param in inspect.signature(callback).parameters.values():
            event = None if param.annotation is inspect.Signature.empty else param.annotation
            break  # only check the first parameter

    if event is None:
        event = Raw

    if not inspect.iscoroutinefunction(callback):
        raise TypeError(f'callback was not an async def function: {callback!r}')

    if not isinstance(event, type):
        raise TypeError(f'event type was not a type (an instance of something was probably used): {event!r}')

    if not isinstance(priority, int):
        raise TypeError(f'priority was not an integer: {priority!r}')

    if not issubclass(event, EventBuilder):
        try:
            if event.SUBCLASS_OF_ID != 0x9f89304e:
                raise TypeError(f'invalid raw update type for the event handler: {event!r}')

            if 'types' in filters:
                warnings.warn('"types" filter is ignored when the event type already is a raw update')

            filters['types'] = event
            event = Raw
        except AttributeError:
            raise TypeError(f'unrecognized event handler type: {param.annotation!r}')

    handler = EventHandler(event, callback, priority, make_filter(**filters))

    if self._dispatching_update_handlers:
        # Now that there's a copy, we're no longer dispatching from the old update_handlers,
        # so we can modify it. This is why we can turn the flag off.
        self._update_handlers = self._update_handlers[:]
        self._dispatching_update_handlers = False

    bisect.insort(self._update_handlers, handler)
    return handler

def remove_event_handler(
        self: 'TelegramClient',
        callback=None,
        event=None,
        *,
        priority=None,
):
    if callback is None and event is None and priority is None:
        raise ValueError('must specify at least one of callback, event or priority')

    if not self._update_handlers:
        return []  # won't be removing anything (some code paths rely on non-empty lists)

    if self._dispatching_update_handlers:
        # May be an unnecessary copy if nothing was removed, but that's not a big deal.
        self._update_handlers = self._update_handlers[:]
        self._dispatching_update_handlers = False

    if isinstance(callback, EventHandler):
        if event is not None or priority is not None:
            warnings.warn('event and priority are ignored when removing EventHandler instances')

        index = bisect.bisect_left(self._update_handlers, callback)
        try:
            if self._update_handlers[index] == callback:
                return [self._update_handlers.pop(index)]
        except IndexError:
            pass
        return []

    if priority is not None:
        # can binary-search (using a dummy EventHandler)
        index = bisect.bisect_right(self._update_handlers, EventHandler(None, None, priority, None))
        try:
            while self._update_handlers[index].priority == priority:
                index += 1
        except IndexError:
            pass

        removed = []
        while index > 0 and self._update_handlers[index - 1].priority == priority:
            index -= 1
            if callback is not None and self._update_handlers[index].callback != callback:
                continue
            if event is not None and self._update_handlers[index].event != event:
                continue
            removed.append(self._update_handlers.pop(index))

        return removed

    # slow-path, remove all matching
    removed = []
    for index in reversed(range(len(self._update_handlers))):
        handler = self._update_handlers[index]
        if callback is not None and handler._callback != callback:
            continue
        if event is not None and handler._event != event:
            continue
        removed.append(self._update_handlers.pop(index))

    return removed

def list_event_handlers(self: 'TelegramClient')\
        -> 'typing.Sequence[typing.Tuple[Callback, EventBuilder]]':
    return self._update_handlers[:]

async def catch_up(self: 'TelegramClient'):
    # The update loop is probably blocked on either timeout or an update to arrive.
    # Unblock the loop by pushing a dummy update which will always trigger a gap.
    # This, in return, causes the update loop to catch up.
    await self._updates_queue.put(_tl.UpdatesTooLong())

async def _update_loop(self: 'TelegramClient'):
    try:
        updates_to_dispatch = deque()
        while self.is_connected:
            if updates_to_dispatch:
                await _dispatch(self, *updates_to_dispatch.popleft())
                continue

            get_diff = self._message_box.get_difference()
            if get_diff:
                self._log[__name__].info('Getting difference for account updates')
                diff = await self(get_diff)
                updates, users, chats = self._message_box.apply_difference(diff, self._entity_cache)
                updates_to_dispatch.extend(_preprocess_updates(self, updates, users, chats))
                continue

            get_diff = self._message_box.get_channel_difference(self._entity_cache)
            if get_diff:
                self._log[__name__].info('Getting difference for channel updates')
                diff = await self(get_diff)
                updates, users, chats = self._message_box.apply_channel_difference(get_diff, diff, self._entity_cache)
                updates_to_dispatch.extend(_preprocess_updates(self, updates, users, chats))
                continue

            deadline = self._message_box.check_deadlines()
            try:
                updates = await asyncio.wait_for(
                    self._updates_queue.get(),
                    deadline - asyncio.get_running_loop().time()
                )
            except asyncio.TimeoutError:
                self._log[__name__].info('Timeout waiting for updates expired')
                continue

            processed = []
            try:
                users, chats = self._message_box.process_updates(updates, self._entity_cache, processed)
            except GapError:
                continue  # get(_channel)_difference will start returning requests

            updates_to_dispatch.extend(_preprocess_updates(self, processed, users, chats))
    except Exception:
        self._log[__name__].exception('Fatal error handling updates (this is a bug in Telethon, please report it)')


def _preprocess_updates(self, updates, users, chats):
    self._entity_cache.extend(users, chats)
    entities = Entities(self, users, chats)
    return ((u, entities) for u in updates)


class Entities:
    def __init__(self, client, users, chats):
        self.self_id = client._session_state.user_id
        self._client = client
        self._entities = {e.id: e for e in itertools.chain(
            (User._new(client, u) for u in users),
            (Chat._new(client, c) for u in chats),
        )}

    def get(self, peer):
        if not peer:
            return None

        id = utils.get_peer_id(peer)
        try:
            return self._entities[id]
        except KeyError:
            entity = self._client._entity_cache.get(query.user_id)
            if not entity:
                raise RuntimeError('Update is missing a hash but did not trigger a gap')

            self._entities[entity.id] = User(self._client, entity) if entity.is_user else Chat(self._client, entity)
            return self._entities[entity.id]


async def _dispatch(self, update, entities):
    self._dispatching_update_handlers = True
    try:
        event_cache = {}
        for handler in self._update_handlers:
            event = event_cache.get(handler._event)
            if not event:
                # build can fail if we're missing an access hash; we want this to crash
                event_cache[handler._event] = event = handler._event._build(self, update, entities)

            while True:
                # filters can be modified at any time, and there can be any amount of them which are not yet resolved
                try:
                    if handler._filter(event):
                        try:
                            await handler._callback(event)
                        except StopPropagation:
                            return
                        except Exception:
                            name = getattr(handler._callback, '__name__', repr(handler._callback))
                            self._log[__name__].exception('Unhandled exception on %s (this is likely a bug in your code)', name)
                except NotResolved as nr:
                    try:
                        await nr.unresolved.resolve()
                        continue
                    except Exception as e:
                        # we cannot really do much about this; it might be a temporary network issue
                        warnings.warn(f'failed to resolve filter, handler will be skipped: {e}: {nr.unresolved!r}')
                except Exception as e:
                    # invalid filter (e.g. types when types were not used as input)
                    warnings.warn(f'invalid filter applied, handler will be skipped: {e}: {e.filter!r}')

                # we only want to continue on unresolved filter (to check if there are more unresolved)
                break
    finally:
        self._dispatching_update_handlers = False
