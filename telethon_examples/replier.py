#!/usr/bin/env python3
# A script to automatically send messages based on certain triggers
from getpass import getpass
from collections import defaultdict
from datetime import datetime, timedelta
from os import environ
# environ is used to get API information from environment variables
# You could also use a config file, pass them as arguments,
# or even hardcode them (not recommended)
from nltk.tokenize import word_tokenize
# NLTK is used to match specific triggers in messages
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.tl.types import UpdateNewChannelMessage, UpdateShortMessage, MessageService
from telethon.tl.functions.messages import EditMessageRequest

# Uncomment this for debugging
# import logging
# logging.basicConfig(level=logging.DEBUG)
# logging.debug('dbg')
# logging.info('info')

REACTS = {'emacs': 'Needs more vim',
          'chrome': 'Needs more Firefox'}

def setup():
    try:
        global recent_reacts
        # A list of dates of reactions we've sent, so we can keep track of floods
        recent_reacts = defaultdict(list)

        global client
        session_name = environ.get('TG_SESSION', 'session')
        user_phone = environ['TG_PHONE']
        client = TelegramClient(session_name,
                                int(environ['TG_API_ID']),
                                environ['TG_API_HASH'],
                                proxy=None,
                                update_workers=4)

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
        print('INFO: Client initialized succesfully!')

        client.add_update_handler(update_handler)
        input('Press Enter to stop this!\n')
    finally:
        client.disconnect()

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
        words = word_tokenize(msg.message)
        for trigger, response in REACTS.items():
            if len(recent_reacts[msg.to_id.channel_id]) > 3:
                break
                # Silently ignore triggers if we've recently sent three reactions
            if trigger in words:
                recent_reacts[msg.to_id.channel_id] = [
                    a for a in recent_reacts[msg.to_id.channel_id] if
                    datetime.now() - a < timedelta(minutes=10)]
                # Remove recents older than 10 minutes
                client.send_message(msg.to_id, response, reply_to=msg.id)
                # Send a reaction
                recent_reacts[msg.to_id.channel_id].append(datetime.now())
                # Add this reaction to the recents list


    if isinstance(update, UpdateShortMessage):
        words = word_tokenize(msg)
        for trigger, response in REACTS.items():
            if len(recent_reacts[update.user_id]) > 3:
                break
                # Silently ignore triggers if we've recently sent three reactions
            if trigger in words:
                recent_reacts[update.user_id] = [
                    a for a in recent_reacts[update.user_id] if
                    datetime.now() - a < timedelta(minutes=10)]
                # Remove recents older than 10 minutes
                client.send_message(update.user_id, response, reply_to=update.id)
                # Send a reaction
                recent_reacts[update.user_id].append(datetime.now())
                # Add this reaction to the recents list

    # Automatically send relevant media when we say certain things
    # When invoking requests, get_input_entity needs to be called manually
    if isinstance(update, UpdateNewChannelMessage) and msg.out:
        if msg.message.lower() == 'x files theme':
            client.send_voice_note(msg.to_id, 'xfiles.m4a', reply_to=msg.id)
        if msg.message.lower() == 'anytime':
            client.send_file(msg.to_id, 'anytime.png', reply_to=msg.id)
        if '.shrug' in msg.message:
            client(
                EditMessageRequest(client.get_input_entity(msg.to_id), msg.id,
                                   message=msg.message.replace('.shrug', r'¯\_(ツ)_/¯')))
 
    if isinstance(update, UpdateShortMessage) and update.out:
        if msg.lower() == 'x files theme':
            client.send_voice_note(update.user_id, 'xfiles.m4a', reply_to=update.id)
        if msg.lower() == 'anytime':
            client.send_file(update.user_id, 'anytime.png', reply_to=update.id)
        if '.shrug' in msg:
            client(
                EditMessageRequest(client.get_input_entity(update.user_id), update.id,
                                   message=msg.replace('.shrug', r'¯\_(ツ)_/¯')))




if __name__ == '__main__':
    setup()
