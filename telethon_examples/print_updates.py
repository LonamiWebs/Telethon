#!/usr/bin/env python3
# A simple script to print all updates received.
# Import modules to access environment, sleep, write to stderr
import os
import sys
import time

# Import the client
from telethon import TelegramClient


# This is a helper method to access environment variables or
# prompt the user to type them in the terminal if missing.
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


# Define some variables so the code reads easier
session = os.environ.get('TG_SESSION', 'printer')
api_id = get_env('TG_API_ID', 'Enter your API ID: ', int)
api_hash = get_env('TG_API_HASH', 'Enter your API hash: ')
proxy = None  # https://github.com/Anorov/PySocks


# This is our update handler. It is called when a new update arrives.
async def handler(update):
    print(update)


# Use the client in a `with` block. It calls `start/disconnect` automatically.
with TelegramClient(session, api_id, api_hash, proxy=proxy) as client:
    # Register the update handler so that it gets called
    client.add_event_handler(handler)

    # Run the client until Ctrl+C is pressed, or the client disconnects
    print('(Press Ctrl+C to stop this)')
    client.run_until_disconnected()
