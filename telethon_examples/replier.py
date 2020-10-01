#!/usr/bin/env python3
"""
A example script to automatically send messages based on certain triggers.

This script assumes that you have certain files on the working directory,
such as "xfiles.m4a" or "anytime.png" for some of the automated replies.
"""
import os
import sys
import time
from collections import defaultdict

from telethon import TelegramClient, events

import logging
logging.basicConfig(level=logging.WARNING)

# "When did we last react?" dictionary, 0.0 by default
recent_reacts = defaultdict(float)


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


def can_react(chat_id):
    # Get the time when we last sent a reaction (or 0)
    last = recent_reacts[chat_id]

    # Get the current time
    now = time.time()

    # If 10 minutes as seconds have passed, we can react
    if now - last < 10 * 60:
        # Make sure we updated the last reaction time
        recent_reacts[chat_id] = now
        return True
    else:
        return False


# Register `events.NewMessage` before defining the client.
# Once you have a client, `add_event_handler` will use this event.
@events.register(events.NewMessage)
async def handler(event):
    # There are better ways to do this, but this is simple.
    # If the message is not outgoing (i.e. someone else sent it)
    if not event.out:
        if 'emacs' in event.raw_text:
            if can_react(event.chat_id):
                await event.reply('> emacs\nneeds more vim')

        elif 'vim' in event.raw_text:
            if can_react(event.chat_id):
                await event.reply('> vim\nneeds more emacs')

        elif 'chrome' in event.raw_text:
            if can_react(event.chat_id):
                await event.reply('> chrome\nneeds more firefox')

    # Reply always responds as a reply. We can respond without replying too
    if 'shrug' in event.raw_text:
        if can_react(event.chat_id):
            await event.respond(r'¯\_(ツ)_/¯')

    # We can also use client methods from here
    client = event.client

    # If we sent the message, we are replying to someone,
    # and we said "save pic" in the message
    if event.out and event.is_reply and 'save pic' in event.raw_text:
        reply_msg = await event.get_reply_message()
        replied_to_user = await reply_msg.get_input_sender()

        message = await event.reply('Downloading your profile photo...')
        file = await client.download_profile_photo(replied_to_user)
        await message.edit('I saved your photo in {}'.format(file))


client = TelegramClient(
    os.environ.get('TG_SESSION', 'replier'),
    get_env('TG_API_ID', 'Enter your API ID: ', int),
    get_env('TG_API_HASH', 'Enter your API hash: '),
    proxy=None
)

with client:
    # This remembers the events.NewMessage we registered before
    client.add_event_handler(handler)

    print('(Press Ctrl+C to stop this)')
    client.run_until_disconnected()
