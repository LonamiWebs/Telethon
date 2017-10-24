#!/usr/bin/env python3
# A simple script to print all updates received

from telethon import TelegramClient
from getpass import getpass
from os import environ
# environ is used to get API information from environment variables
# You could also use a config file, pass them as arguments, 
# or even hardcode them (not recommended)

def main():
    session_name = environ.get('TG_SESSION','session')
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
                pw = getpass('Two step verification enabled. Please enter your password: ')
                code_ok = client.sign_in(password=pw)
    print('INFO: Client initialized succesfully!')

    client.add_update_handler(update_handler)
    input('Press Enter to stop this!\n')

def update_handler(update):
    print(update) 
    print('Press Enter to stop this!')

if __name__ == '__main__':
    main()
