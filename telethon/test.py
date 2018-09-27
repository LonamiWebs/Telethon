import inspect
import asyncio
from telethon.utils import AsyncClassWrapper

class session:
    test1='test1'
    async def test2(self,arg):
        print(arg)

    def test3(self,arg):
        print("test3")

    @property
    def test4(self):
        return "test4"

async def t():
    s = AsyncClassWrapper(session())
    print(s.test1)
    await s.test2("test2")
    await s.test3("k")
    print(s.test4)
    s.test5 = "hey"
    print(s.test5)



asyncio.get_event_loop().run_until_complete(t())
import inspect
import asyncio
from telethon.client import TelegramClient



api_hash = ""
api_id = 12345
async def main():
    client = TelegramClient(None, api_id, api_hash)
    await client.session.set_dc(2, '149.154.167.40', 443)
    await client.start(
        phone='9996621234', code_callback=lambda: '22222'
    )
    print(await client.get_dialogs())
    await client.send_message("me","heyh")


asyncio.get_event_loop().run_until_complete(main())