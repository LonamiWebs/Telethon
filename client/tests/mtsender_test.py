import asyncio
import logging

from pytest import LogCaptureFixture, mark
from telethon._impl.mtproto import Full
from telethon._impl.mtsender import connect
from telethon._impl.session import DataCenter
from telethon._impl.tl import LAYER, abcs, functions, types

TELEGRAM_TEST_DC = 2, "149.154.167.40:443"

TEST_TIMEOUT = 10000


@mark.net
async def test_invoke_encrypted_method(caplog: LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)

    deadline = asyncio.get_running_loop().time() + TEST_TIMEOUT

    def timeout() -> float:
        return deadline - asyncio.get_running_loop().time()

    sender = await asyncio.wait_for(connect(Full(), *TELEGRAM_TEST_DC), timeout())

    rx = sender.enqueue(
        functions.invoke_with_layer(
            layer=LAYER,
            query=functions.init_connection(
                api_id=1,
                device_model="Test",
                system_version="0.1",
                app_version="0.1",
                system_lang_code="en",
                lang_pack="",
                lang_code="",
                proxy=None,
                params=None,
                query=functions.help.get_nearest_dc(),
            ),
        )
    )

    while True:
        await asyncio.wait_for(sender.step(), timeout=timeout())
        if rx.done():
            nearest = abcs.NearestDc.from_bytes(rx.result())
            assert isinstance(nearest, types.NearestDc)
            break
