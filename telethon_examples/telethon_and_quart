from quart import Quart
from telethon import TelegramClient, events
import asyncio
import json

loop = asyncio.get_event_loop()
app = Quart(__name__)

TELEGREM_TOKEN = "complete me"
API_ID = 0 # complete me
API_HASH = 'complete me'

messages_list = []


class Telegrem:
    def __init__(self, bot_token, api_id, api_hash):
        self.bot_token = bot_token
        self.api_id = api_id
        self.api_hash = api_hash
        self.client = TelegramClient('bot', api_id, api_hash)

    async def receive_message(self, event):
        print(f'message is here {event.raw_text}')
        messages_list.append(event.raw_text)

    async def start_polling(self):
        await self.client.start(bot_token=self.bot_token)
        self.client.add_event_handler(self.receive_message, events.NewMessage)


async def background():
    telegrem = Telegrem(TELEGREM_TOKEN, API_ID, API_HASH)
    loop.create_task(telegrem.start_polling())


@app.route('/')
async def hello():
    return json.dumps(messages_list)

loop.create_task(background())
app.run(loop=loop)
