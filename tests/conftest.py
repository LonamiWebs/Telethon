import pytest


pytestmark = pytest.mark.asyncio


@pytest.fixture
async def bot(request):
    import os
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    cl = TelegramClient(StringSession(os.environ['BOT_SESSION']), 1, '-')

    def fin():
        cl.disconnect()  # note: this runs the loop

    request.addfinalizer(fin)

    await cl.start()
    return cl


@pytest.fixture
async def client(request):
    import os
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    cl = TelegramClient(StringSession(os.environ['CLIENT_SESSION']), 1, '-')

    def fin():
        cl.disconnect()  # note: this runs the loop

    request.addfinalizer(fin)

    await cl.start()
    return cl
