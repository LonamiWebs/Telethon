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

from .client.telegramclient import TelegramClient
from .tl.custom import Draft, Dialog, MessageButton, Forward, Message


def _syncify(t, method_name):
    method = getattr(t, method_name)

    @functools.wraps(method)
    def syncified(*args, **kwargs):
        coro = method(*args, **kwargs)
        return (
            coro if asyncio.get_event_loop().is_running()
            else asyncio.get_event_loop().run_until_complete(coro)
        )

    setattr(t, method_name, syncified)


def syncify(*types):
    """
    Converts all the methods in the given types (class definitions)
    into synchronous, which return either the coroutine or the result
    based on whether ``asyncio's`` event loop is running.
    """
    for t in types:
        for method_name in dir(t):
            if not method_name.startswith('_') or method_name == '__call__':
                if inspect.iscoroutinefunction(getattr(t, method_name)):
                    _syncify(t, method_name)


syncify(TelegramClient, Draft, Dialog, MessageButton, Forward, Message)
