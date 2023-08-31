import asyncio
import logging

from telethon._impl.mtproto.transport.full import Full
from telethon._impl.mtsender.sender import connect

TELEGRAM_TEST_DC_2 = "149.154.167.40:443"

TELEGRAM_DEFAULT_TEST_DC = TELEGRAM_TEST_DC_2

TEST_TIMEOUT = 10000


def test_invoke_encrypted_method(caplog) -> None:
    caplog.set_level(logging.DEBUG)

    async def func():
        deadline = asyncio.get_running_loop().time() + TEST_TIMEOUT

        def timeout():
            return deadline - asyncio.get_running_loop().time()

        sender, enqueuer = await asyncio.wait_for(
            connect(Full(), TELEGRAM_DEFAULT_TEST_DC), timeout()
        )

        # TODO test enqueuer
        sender, enqueuer

    asyncio.run(func())
