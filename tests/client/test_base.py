import pytest

from telethon import types

pytestmark = pytest.mark.asyncio


async def test_get_me(client):
    me = await client.get_me()
    assert isinstance(me, types.User)
