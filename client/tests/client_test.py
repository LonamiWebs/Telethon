import os
import random

from pytest import mark
from telethon._impl.client.client.client import Client
from telethon._impl.client.client.net import Config
from telethon._impl.session.message_box.defs import Session
from telethon._impl.tl.mtproto import functions, types


@mark.api
@mark.net
async def test_ping_pong() -> None:
    api_id = os.getenv("TG_ID")
    api_hash = os.getenv("TG_HASH")
    assert api_id and api_id.isdigit()
    assert api_hash
    client = Client(
        Config(
            session=Session(
                dcs=[],
                user=None,
                state=None,
            ),
            api_id=int(api_id),
            api_hash=api_hash,
        )
    )
    assert not client.connected
    await client.connect()
    assert client.connected

    ping_id = random.randrange(-(2**63), 2**63)
    pong = await client(functions.ping(ping_id=ping_id))
    assert isinstance(pong, types.Pong)
    assert pong.ping_id == ping_id
