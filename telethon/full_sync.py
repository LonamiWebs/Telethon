"""
This magical module will rewrite all public methods in the public interface of
the library so they can delegate the call to an asyncio event loop in another
thread and wait for the result. This rewrite may not be desirable if the end
user always uses the methods they way they should be ran, but it's incredibly
useful for quick scripts and legacy code.
"""
import asyncio
import functools
import inspect
import threading
from concurrent.futures import Future, ThreadPoolExecutor

from async_generator import isasyncgenfunction

from .client.telegramclient import TelegramClient
from .tl.custom import (
    Draft, Dialog, MessageButton, Forward, Message, InlineResult, Conversation
)
from .tl.custom.chatgetter import ChatGetter
from .tl.custom.sendergetter import SenderGetter


async def _proxy_future(af, cf):
    try:
        res = await af
        cf.set_result(res)
    except Exception as e:
        cf.set_exception(e)


def _sync_result(loop, x):
    f = Future()
    loop.call_soon_threadsafe(asyncio.ensure_future, _proxy_future(x, f))
    return f.result()


class _SyncGen:
    def __init__(self, loop, gen):
        self.loop = loop
        self.gen = gen

    def __iter__(self):
        return self

    def __next__(self):
        try:
            return _sync_result(self.loop, self.gen.__anext__())
        except StopAsyncIteration:
            raise StopIteration from None


def _syncify_wrap(t, method_name, loop, thread_name, syncifier=_sync_result):
    method = getattr(t, method_name)

    @functools.wraps(method)
    def syncified(*args, **kwargs):
        coro = method(*args, **kwargs)
        return (
            coro if threading.current_thread().name == thread_name
            else syncifier(loop, coro)
        )

    setattr(t, method_name, syncified)


def _syncify(*types, loop, thread_name):
    for t in types:
        for method_name in dir(t):
            if not method_name.startswith('_') or method_name == '__call__':
                if inspect.iscoroutinefunction(getattr(t, method_name)):
                    _syncify_wrap(t, method_name, loop, thread_name, _sync_result)
                elif isasyncgenfunction(getattr(t, method_name)):
                    _syncify_wrap(t, method_name, loop, thread_name, _SyncGen)


__asyncthread = None


def enable(loop=None, thread_name="__telethon_async_thread__"):
    global __asyncthread
    if __asyncthread is not None:
        raise RuntimeError("full_sync can only be enabled once")

    if not loop:
        loop = asyncio.get_event_loop()

    TelegramClient.__init__ = functools.partialmethod(TelegramClient.__init__,
                                                      loop=loop)

    _syncify(TelegramClient, Draft, Dialog, MessageButton, ChatGetter,
             SenderGetter, Forward, Message, InlineResult, Conversation,
             loop=loop, thread_name=thread_name)
    _syncify_wrap(TelegramClient, "start", loop, thread_name)

    old_add_event_handler = TelegramClient.add_event_handler
    old_remove_event_handler = TelegramClient.remove_event_handler
    proxied_event_handlers = {}

    @functools.wraps(old_add_event_handler)
    def add_proxied_event_handler(self, callback, *args, **kwargs):
        async def _proxy(event):
            h_t = threading.Thread(target=callback, args=(event,))
            h_t.start()

        proxied_event_handlers[callback] = _proxy

        args = (self, callback, *args)
        return old_add_event_handler(*args, **kwargs)

    @functools.wraps(old_remove_event_handler)
    def remove_proxied_event_handler(self, callback, *args, **kwargs):
        args = (self, proxied_event_handlers.get(callback, callback), *args)
        return old_remove_event_handler(*args, **kwargs)

    TelegramClient.add_event_handler = add_proxied_event_handler
    TelegramClient.remove_event_handler = remove_proxied_event_handler

    def run_until_disconnected(self):
        return _sync_result(loop, self._run_until_disconnected())

    TelegramClient.run_until_disconnected = run_until_disconnected

    def start():
        asyncio.set_event_loop(loop)
        loop.run_forever()

    __asyncthread = threading.Thread(target=start, name=thread_name,
                                     daemon=True)
    __asyncthread.start()
    __asyncthread.loop = loop
    return __asyncthread


def stop():
    global __asyncthread
    if not __asyncthread:
        raise RuntimeError("Can't find asyncio thread")
    __asyncthread.loop.call_soon_threadsafe(__asyncthread.loop.stop)
