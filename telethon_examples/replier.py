#!/usr/bin/env python3
"""
A example script to automatically send messages based on certain triggers.

The script makes uses of environment variables to determine the API ID,
hash, phone and such to be used. You may want to add these to your .bashrc
file, including TG_API_ID, TG_API_HASH, TG_PHONE and optionally TG_SESSION.

This script assumes that you have certain files on the working directory,
such as "xfiles.m4a" or "anytime.png" for some of the automated replies.
"""
from getpass import getpass
from collections import defaultdict
from datetime import datetime, timedelta
from os import environ

import re

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.tl.types import UpdateNewChannelMessage, UpdateShortMessage, MessageService
from telethon.tl.functions.messages import EditMessageRequest

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


def update_handler(update):
    global recent_reacts
    try:
        msg = update.message
    except AttributeError:
        # print(update, 'did not have update.message')
        return
    if isinstance(msg, MessageService):
        print(msg, 'was service msg')
        return

    # React to messages in supergroups and PMs
    if isinstance(update, UpdateNewChannelMessage):
        words = re.split('\W+', msg.message)
        for trigger, response in REACTS.items():
            if len(recent_reacts[msg.to_id.channel_id]) > 3:
                # Silently ignore triggers if we've recently sent 3 reactions
                break

            if trigger in words:
                # Remove recent replies older than 10 minutes
                recent_reacts[msg.to_id.channel_id] = [
                    a for a in recent_reacts[msg.to_id.channel_id] if
                    datetime.now() - a < timedelta(minutes=10)
                ]
                # Send a reaction
                client.send_message(msg.to_id, response, reply_to=msg.id)
                # Add this reaction to the list of recent actions
                recent_reacts[msg.to_id.channel_id].append(datetime.now())

    if isinstance(update, UpdateShortMessage):
        words = re.split('\W+', msg)
        for trigger, response in REACTS.items():
            if len(recent_reacts[update.user_id]) > 3:
                # Silently ignore triggers if we've recently sent 3 reactions
                break

            if trigger in words:
                # Send a reaction
                client.send_message(update.user_id, response, reply_to=update.id)
                # Add this reaction to the list of recent reactions
                recent_reacts[update.user_id].append(datetime.now())

    # Automatically send relevant media when we say certain things
    # When invoking requests, get_input_entity needs to be called manually
    if isinstance(update, UpdateNewChannelMessage) and msg.out:
        if msg.message.lower() == 'x files theme':
            client.send_voice_note(msg.to_id, 'xfiles.m4a', reply_to=msg.id)
        if msg.message.lower() == 'anytime':
            client.send_file(msg.to_id, 'anytime.png', reply_to=msg.id)
        if '.shrug' in msg.message:
            client(EditMessageRequest(
                client.get_input_entity(msg.to_id), msg.id,
                message=msg.message.replace('.shrug', r'¯\_(ツ)_/¯')
            ))
 
    if isinstance(update, UpdateShortMessage) and update.out:
        if msg.lower() == 'x files theme':
            client.send_voice_note(update.user_id, 'xfiles.m4a', reply_to=update.id)
        if msg.lower() == 'anytime':
            client.send_file(update.user_id, 'anytime.png', reply_to=update.id)
        if '.shrug' in msg:
            client(EditMessageRequest(
                client.get_input_entity(update.user_id), update.id,
                message=msg.replace('.shrug', r'¯\_(ツ)_/¯')
            ))


if __name__ == '__main__':
    session_name = environ.get('TG_SESSION', 'session')
    user_phone = environ['TG_PHONE']
    client = TelegramClient(
        session_name, int(environ['TG_API_ID']), environ['TG_API_HASH'],
        proxy=None, update_workers=4
    )
    try:
        print('INFO: Connecting to Telegram Servers...', end='', flush=True)
        client.connect()
        print('Done!')

        if not client.is_user_authorized():
            print('INFO: Unauthorized user')
            client.send_code_request(user_phone)
            code_ok = False
            while not code_ok:
                code = input('Enter the auth code: ')
                try:
                    code_ok = client.sign_in(user_phone, code)
                except SessionPasswordNeededError:
                    password = getpass('Two step verification enabled. '
                                       'Please enter your password: ')
                    code_ok = client.sign_in(password=password)
        print('INFO: Client initialized successfully!')

        client.add_update_handler(update_handler)
        input('Press Enter to stop this!\n')
    except KeyboardInterrupt:
        pass
    finally:
        client.disconnect()
