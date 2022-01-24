import asyncio
import inspect
import itertools
import random
import sys
import time
import traceback
import typing
import logging
from collections import deque

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
