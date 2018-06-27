#!/usr/bin/env python3
# A simple script to print all updates received
#
# NOTE: To run this script you MUST have 'TG_API_ID' and 'TG_API_HASH' in
#       your environment variables. This is a good way to use these private
#       values. See https://superuser.com/q/284342.
from os import environ

from telethon import TelegramClient


client = TelegramClient(
    environ.get('TG_SESSION', 'session'),
    environ['TG_API_ID'],
    environ['TG_API_HASH'],
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
