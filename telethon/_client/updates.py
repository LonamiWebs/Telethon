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
from .._events.filters import make_filter
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
            if not issubclass(param.annotation, EventBuilder):
                raise TypeError(f'unrecognized event handler type: {param.annotation!r}')
            event = param.annotation
            break  # only check the first parameter

    if event is None:
        event = Raw

    handler = EventHandler(event, callback, priority, make_filter(**filters))
    bisect.insort(self._update_handlers, handler)
    return handler

def remove_event_handler(
        self: 'TelegramClient',
        callback,
        event,
        priority,
):
    if callback is None and event is None and priority is None:
        raise ValueError('must specify at least one of callback, event or priority')

    if not self._update_handlers:
        return []  # won't be removing anything (some code paths rely on non-empty lists)

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
    for index, handler in reversed(enumerate(self._update_handlers)):
        if callback is not None and handler.callback != callback:
            continue
        if event is not None and handler.event != event:
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
        while self.is_connected():
            if updates_to_dispatch:
                # TODO dispatch
                updates_to_dispatch.popleft()
                continue

            get_diff = self._message_box.get_difference()
            if get_diff:
                self._log[__name__].info('Getting difference for account updates')
                diff = await self(get_diff)
                updates, users, chats = self._message_box.apply_difference(diff, self._entity_cache)
                self._entity_cache.extend(users, chats)
                updates_to_dispatch.extend(updates)
                continue

            get_diff = self._message_box.get_channel_difference(self._entity_cache)
            if get_diff:
                self._log[__name__].info('Getting difference for channel updates')
                diff = await self(get_diff)
                updates, users, chats = self._message_box.apply_channel_difference(get_diff, diff, self._entity_cache)
                self._entity_cache.extend(users, chats)
                updates_to_dispatch.extend(updates)
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
            users, chats = self._message_box.process_updates(updates, self._entity_cache, processed)
            self._entity_cache.extend(users, chats)
            updates_to_dispatch.extend(processed)
    except Exception:
        self._log[__name__].exception('Fatal error handling updates (this is a bug in Telethon, please report it)')
