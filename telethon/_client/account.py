import functools
import inspect
import typing
import dataclasses
import asyncio
from contextvars import ContextVar

from .._misc import helpers, utils
from .. import _tl

if typing.TYPE_CHECKING:
    from .telegramclient import TelegramClient


ignore_takeout = ContextVar('ignore_takeout', default=False)


# TODO Make use of :tl:`InvokeWithMessagesRange` somehow
#      For that, we need to use :tl:`GetSplitRanges` first.
class _Takeout:
    def __init__(self, client, kwargs):
        self._client = client
        self._kwargs = kwargs

    async def __aenter__(self):
        await self._client.begin_takeout(**self._kwargs)
        return self._client

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self._client.end_takeout(success=exc_type is None)


def takeout(self: 'TelegramClient', **kwargs):
    return _Takeout(self, kwargs)


async def begin_takeout(
    self: 'TelegramClient',
    *,
    contacts: bool = None,
    users: bool = None,
    chats: bool = None,
    megagroups: bool = None,
    channels: bool = None,
    files: bool = None,
    max_file_size: bool = None,
) -> 'TelegramClient':
    if self.takeout_active:
        raise ValueError('a previous takeout session was already active')

    takeout = await self(_tl.fn.account.InitTakeoutSession(
        contacts=contacts,
        message_users=users,
        message_chats=chats,
        message_megagroups=megagroups,
        message_channels=channels,
        files=files,
        file_max_size=max_file_size
    ))
    await self._replace_session_state(takeout_id=takeout.id)


def takeout_active(self: 'TelegramClient') -> bool:
    return self._session_state.takeout_id is not None


async def end_takeout(self: 'TelegramClient', *, success: bool) -> bool:
    if not self.takeout_active:
        raise ValueError('no previous takeout session was active')

    result = await self(_tl.fn.account.FinishTakeoutSession(success))
    if not result:
        raise ValueError("could not end the active takeout session")

    await self._replace_session_state(takeout_id=None)
