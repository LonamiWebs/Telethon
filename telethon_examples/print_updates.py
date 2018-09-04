#!/usr/bin/env python3
# A simple script to print all updates received
import os
import sys
import time

from telethon import TelegramClient


def get_env(name, message, cast=str):
    if name in os.environ:
        return os.environ[name]
    while True:
        value = input(message)
        try:
            return cast(value)
        except ValueError as e:
            print(e, file=sys.stderr)
            time.sleep(1)


client = TelegramClient(
    os.environ.get('TG_SESSION', 'printer'),
    get_env('TG_API_ID', 'Enter your API ID: ', int),
    get_env('TG_API_HASH', 'Enter your API hash: '),
    proxy=None
)


async def update_handler(update):
    print(update)


client.add_event_handler(update_handler)

'''You could also have used the @client.on(...) syntax:
from telethon import events

@client.on(events.Raw)
async def update_handler(update):
    print(update)
'''

with client.start():
    print('(Press Ctrl+C to stop this)')
    client.run_until_disconnected()
