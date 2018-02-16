#!/usr/bin/env python3
"""
A example script to automatically send messages based on certain triggers.

The script makes uses of environment variables to determine the API ID,
hash, phone and such to be used. You may want to add these to your .bashrc
file, including TG_API_ID, TG_API_HASH, TG_PHONE and optionally TG_SESSION.

This script assumes that you have certain files on the working directory,
such as "xfiles.m4a" or "anytime.png" for some of the automated replies.
"""
import re
from collections import defaultdict
from datetime import datetime, timedelta
from os import environ

from telethon import TelegramClient, events, utils

"""Uncomment this for debugging
import logging
logging.basicConfig(level=logging.DEBUG)
logging.debug('dbg')
logging.info('info')
"""

REACTS = {'emacs': 'Needs more vim',
          'chrome': 'Needs more Firefox'}

# A list of dates of reactions we've sent, so we can keep track of floods
recent_reacts = defaultdict(list)


if __name__ == '__main__':
    # TG_API_ID and TG_API_HASH *must* exist or this won't run!
    session_name = environ.get('TG_SESSION', 'session')
    client = TelegramClient(
        session_name, int(environ['TG_API_ID']), environ['TG_API_HASH'],
        spawn_read_thread=False, proxy=None, update_workers=4
    )

    @client.on(events.NewMessage)
    def my_handler(event: events.NewMessage.Event):
        global recent_reacts

        # This utils function gets the unique identifier from peers (to_id)
        to_id = utils.get_peer_id(event.message.to_id)

        # Through event.raw_text we access the text of messages without format
        words = re.split('\W+', event.raw_text)

        # Try to match some reaction
        for trigger, response in REACTS.items():
            if len(recent_reacts[to_id]) > 3:
                # Silently ignore triggers if we've recently sent 3 reactions
                break

            if trigger in words:
                # Remove recent replies older than 10 minutes
                recent_reacts[to_id] = [
                    a for a in recent_reacts[to_id] if
                    datetime.now() - a < timedelta(minutes=10)
                ]
                # Send a reaction as a reply (otherwise, event.respond())
                event.reply(response)
                # Add this reaction to the list of recent actions
                recent_reacts[to_id].append(datetime.now())

        # Automatically send relevant media when we say certain things
        # When invoking requests, get_input_entity needs to be called manually
        if event.out:
            if event.raw_text.lower() == 'x files theme':
                client.send_voice_note(event.message.to_id, 'xfiles.m4a',
                                       reply_to=event.message.id)
            if event.raw_text.lower() == 'anytime':
                client.send_file(event.message.to_id, 'anytime.png',
                                 reply_to=event.message.id)
            if '.shrug' in event.text:
                event.edit(event.text.replace('.shrug', r'¯\_(ツ)_/¯'))

    if 'TG_PHONE' in environ:
        client.start(phone=environ['TG_PHONE'])
    else:
        client.start()

    print('(Press Ctrl+C to stop this)')
    client.idle()
