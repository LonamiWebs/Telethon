"""
This magical module will rewrite all public methods in the public interface
of the library so they can run the loop on their own if it's not already
running. This rewrite may not be desirable if the end user always uses the
methods they way they should be ran, but it's incredibly useful for quick
scripts and the runtime overhead is relatively low.

Some really common methods which are hardly used offer this ability by
default, such as ``.start()`` and ``.run_until_disconnected()`` (since
you may want to start, and then run until disconnected while using async
event handlers).
"""
import asyncio
import functools
import inspect

from async_generator import isasyncgenfunction

from .client.telegramclient import TelegramClient
from .tl.custom import (
    Draft, Dialog, MessageButton, Forward, Message, InlineResult, Conversation
)
from .tl.custom.chatgetter import ChatGetter
from .tl.custom.sendergetter import SenderGetter


class _SyncGen:
    def __init__(self, gen):
        self.gen = gen

    def __iter__(self):
        return self

    def __next__(self):
        try:
            return asyncio.get_event_loop() \
                .run_until_complete(self.gen.__anext__())
        except StopAsyncIteration:
            raise StopIteration from None


def _syncify_wrap(t, method_name, gen):
    method = getattr(t, method_name)

    @functools.wraps(method)
    def syncified(*args, **kwargs):
        coro = method(*args, **kwargs)
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return coro
        elif gen:
            return _SyncGen(coro)
        else:
            return loop.run_until_complete(coro)

    # Save an accessible reference to the original method
    setattr(syncified, '__tl.sync', method)
    setattr(t, method_name, syncified)


def syncify(*types):
    """
    Converts all the methods in the given types (class definitions)
    into synchronous, which return either the coroutine or the result
    based on whether ``asyncio's`` event loop is running.
    """
    for t in types:
        for name in dir(t):
            if not name.startswith('_') or name == '__call__':
                if inspect.iscoroutinefunction(getattr(t, name)):
                    _syncify_wrap(t, name, gen=False)
                elif isasyncgenfunction(getattr(t, name)):
                    _syncify_wrap(t, name, gen=True)


syncify(TelegramClient, Draft, Dialog, MessageButton,
        ChatGetter, SenderGetter, Forward, Message, InlineResult, Conversation)
