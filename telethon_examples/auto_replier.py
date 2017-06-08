# Example demonstrating how to make an automatic replier
from telethon import TelegramClient
from telethon.tl.types import UpdateShortMessage, UpdateShortChatMessage

from time import sleep


def get_config():
    """Returns (session_name, user_phone, api_id, api_hash)"""
    result = {}
    with open('../api/settings', 'r', encoding='utf-8') as file:
        for line in file:
            value_pair = line.split('=')
            left = value_pair[0].strip()
            right = value_pair[1].strip()
            result[left] = right

    return (
        '../' + result.get('session_name', 'anonymous'),
        result.get('user_phone'),
        int(result.get('api_id')),
        result.get('api_hash')
    )


# Connection
user_id, user_phone, api_id, api_hash = get_config()
client = TelegramClient('session_id', api_id, api_hash)
client.connect()

if not client.is_user_authorized():
    client.send_code_request(user_phone)
    client.sign_in('+34600000000', input('Enter code: '))

number_of_auto_replies = int(input('Auto-reply how many times?: '))


# Real work here
def auto_reply_thread(update_object):
    print(type(update_object), update_object)
    return
'''
if isinstance(update_object, UpdateShortMessage):
    if not update_object.out:
        client.send_message()

        print('[User #{} sent {}]'.format(
            update_object.user_id, update_object.message))

elif isinstance(update_object, UpdateShortChatMessage):
    if not update_object.out:
        print('[Chat #{}, user #{} sent {}]'.format(
               update_object.chat_id, update_object.from_id,
               update_object.message))
'''

client.add_update_handler(auto_reply_thread)
while number_of_auto_replies > 0:
    # A real application would do more work here
    sleep(1)