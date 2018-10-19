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

from . import events
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


def _syncify_wrap(t, method_name, loop, thread_ident,
                  syncifier=_sync_result, rename=None):
    method = getattr(t, method_name)

    @functools.wraps(method)
    def syncified(*args, **kwargs):
        coro = method(*args, **kwargs)
        return (
            coro if threading.get_ident() == thread_ident
            else syncifier(loop, coro)
        )

    setattr(t, rename or method_name, syncified)


def _syncify(*types, loop, thread_ident):
    for t in types:
        # __enter__ and __exit__ need special care (VERY dirty hack).
        #
        # Normally we want them to raise if the loop is running because
        # the user can't await there, and they need the async with variant.
        #
        # However they check if the loop is running to raise, which it is
        # with full_sync enabled, so we patch them with the async variant.
        if hasattr(t, '__aenter__'):
            _syncify_wrap(
                t, '__aenter__', loop, thread_ident, rename='__enter__')

            _syncify_wrap(
                t, '__aexit__', loop, thread_ident, rename='__exit__')

        for name in dir(t):
            if not name.startswith('_') or name == '__call__':
                meth = getattr(t, name)
                meth = getattr(meth, '__tl.sync', meth)
                if inspect.iscoroutinefunction(meth):
                    _syncify_wrap(t, name, loop, thread_ident)
                elif isasyncgenfunction(meth):
                    _syncify_wrap(t, name, loop, thread_ident, _SyncGen)


__asyncthread = None


def enable(*, loop=None, executor=None, max_workers=1):
    """
    Enables the fully synchronous mode. You should enable this at
    the beginning of your script, right after importing, only once.

    **Please** make sure to call `stop` at the end of your script.

    You can define the event loop to use and executor, otherwise
    the default loop and ``ThreadPoolExecutor`` will be used, in
    which case `max_workers` will be passed to it. If you pass a
    custom executor, `max_workers` will be ignored.
    """
    global __asyncthread
    if __asyncthread is not None:
        raise RuntimeError("full_sync can only be enabled once")

    if not loop:
        loop = asyncio.get_event_loop()
    if not executor:
        executor = ThreadPoolExecutor(max_workers=max_workers)

    def start():
        asyncio.set_event_loop(loop)
        loop.run_forever()

    __asyncthread = threading.Thread(
        target=start, name="__telethon_async_thread__", daemon=True
    )
    __asyncthread.start()
    __asyncthread.loop = loop
    __asyncthread.executor = executor

    TelegramClient.__init__ = functools.partialmethod(
        TelegramClient.__init__, loop=loop
    )

    event_cls = filter(None, (
        getattr(getattr(events, name), 'Event', None)
        for name in dir(events)
    ))
    _syncify(TelegramClient, Draft, Dialog, MessageButton, ChatGetter,
             SenderGetter, Forward, Message, InlineResult, Conversation,
             *event_cls,
             loop=loop, thread_ident=__asyncthread.ident)
    _syncify_wrap(TelegramClient, "start", loop, __asyncthread.ident)

    old_add_event_handler = TelegramClient.add_event_handler
    old_remove_event_handler = TelegramClient.remove_event_handler
    proxied_event_handlers = {}

    @functools.wraps(old_add_event_handler)
    def add_proxied_event_handler(self, callback, *args, **kwargs):
        async def _proxy(*pargs, **pkwargs):
            await loop.run_in_executor(
                executor, functools.partial(callback, *pargs, **pkwargs))

        proxied_event_handlers[callback] = _proxy

        args = (self, _proxy, *args)
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

    return __asyncthread


def stop():
    """
    Stops the fully synchronous code. You
    should call this before your script exits.
    """
    global __asyncthread
    if not __asyncthread:
        raise RuntimeError("Can't find asyncio thread")
    __asyncthread.loop.call_soon_threadsafe(__asyncthread.loop.stop)
    __asyncthread.executor.shutdown()
