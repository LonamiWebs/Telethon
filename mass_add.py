from telethon import TelegramClient, events, sync, utils
from telethon.tl.functions.messages import AddChatUserRequest
 
api_id = 28660903
api_hash = '2e6d3d05025f5bd74427d140a45bbc47'

client = TelegramClient('session_name', api_id, api_hash)
client.start()

chat_id = 4094437222
user_to_add = 464929491

# print(client.get_me().stringify())

# client.download_profile_photo('me')
# messages = client.get_messages('username')
# messages[0].download_media()

# @client.on(events.NewMessage(pattern='(?i)hi|hello'))
# async def handler(event):
#     await event.respond('Hey!')
#     await client(AddChatUserRequest(
#         chat_id,
#         user_to_add,
#         fwd_limit=10  # Allow the user to see the 10 last messages
#     ))

client(AddChatUserRequest(
        chat_id,
        user_to_add,
        fwd_limit=100  # Allow the user to see the 100 last messages
    ))

