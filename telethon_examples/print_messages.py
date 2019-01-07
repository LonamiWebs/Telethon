#!/usr/bin/env python3
# A simple script to print some messages.
import os
import sys
import time

from telethon import TelegramClient, events, utils


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


session = os.environ.get('TG_SESSION', 'printer')
api_id = get_env('TG_API_ID', 'Enter your API ID: ', int)
api_hash = get_env('TG_API_HASH', 'Enter your API hash: ')
proxy = None  # https://github.com/Anorov/PySocks

# Create and start the client so we can make requests (we don't here)
client = TelegramClient(session, api_id, api_hash, proxy=proxy).start()


# `pattern` is a regex, see https://docs.python.org/3/library/re.html
# Use https://regexone.com/ if you want a more interactive way of learning.
#
# "(?i)" makes it case-insensitive, and | separates "options".
@client.on(events.NewMessage(pattern=r'(?i).*\b(hello|hi)\b'))
async def handler(event):
    sender = await event.get_sender()
    name = utils.get_display_name(sender)
    print(name, 'said', event.text, '!')

try:
    print('(Press Ctrl+C to stop this)')
    client.run_until_disconnected()
finally:
    client.disconnect()

# Note: We used try/finally to show it can be done this way, but using:
#
#   with client:
#       client.run_until_disconnected()
#
# is almost always a better idea.
