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
    def __init__(self, loop, gen):
        self.loop = loop
        self.gen = gen

    def __iter__(self):
        return self

    def __next__(self):
        try:
            return self.loop.run_until_complete(self.gen.__anext__())
        except StopAsyncIteration:
            raise StopIteration from None


def _syncify_wrap(t, method_name, syncifier):
    method = getattr(t, method_name)

    @functools.wraps(method)
    def syncified(*args, **kwargs):
        coro = method(*args, **kwargs)
        return (
            coro if asyncio.get_event_loop().is_running()
            else syncifier(coro)
        )

    # Save an accessible reference to the original method
    setattr(syncified, '__tl.sync', method)
    setattr(t, method_name, syncified)


def syncify(*types):
    """
    Converts all the methods in the given types (class definitions)
    into synchronous, which return either the coroutine or the result
    based on whether ``asyncio's`` event loop is running.
    """
    loop = asyncio.get_event_loop()
    for t in types:
        for name in dir(t):
            if not name.startswith('_') or name == '__call__':
                if inspect.iscoroutinefunction(getattr(t, name)):
                    _syncify_wrap(t, name, loop.run_until_complete)
                elif isasyncgenfunction(getattr(t, name)):
                    _syncify_wrap(t, name, functools.partial(_SyncGen, loop))


syncify(TelegramClient, Draft, Dialog, MessageButton,
        ChatGetter, SenderGetter, Forward, Message, InlineResult, Conversation)
