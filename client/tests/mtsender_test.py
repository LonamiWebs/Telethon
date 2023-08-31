import asyncio
import logging

from pytest import LogCaptureFixture
from telethon._impl.mtproto.transport.full import Full
from telethon._impl.mtsender.sender import connect
from telethon._impl.tl import LAYER, abcs, functions, types

TELEGRAM_TEST_DC_2 = "149.154.167.40:443"

TELEGRAM_DEFAULT_TEST_DC = TELEGRAM_TEST_DC_2

TEST_TIMEOUT = 10000


def test_invoke_encrypted_method(caplog: LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)

    async def func() -> None:
        deadline = asyncio.get_running_loop().time() + TEST_TIMEOUT

        def timeout() -> float:
            return deadline - asyncio.get_running_loop().time()

        sender, enqueuer = await asyncio.wait_for(
            connect(Full(), TELEGRAM_DEFAULT_TEST_DC), timeout()
        )

        rx = enqueuer.enqueue(
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

    asyncio.run(func())
