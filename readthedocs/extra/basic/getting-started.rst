.. _getting-started:


===============
Getting Started
===============


Simple Installation
*******************

   ``pip3 install telethon``

   **More details**: :ref:`installation`


Creating a client
*****************

   .. code-block:: python

       from telethon import TelegramClient

       # These example values won't work. You must get your own api_id and
       # api_hash from https://my.telegram.org, under API Development.
       api_id = 12345
       api_hash = '0123456789abcdef0123456789abcdef'

       client = TelegramClient('session_name', api_id, api_hash)
       client.start()

   **More details**: :ref:`creating-a-client`


Basic Usage
***********

   .. code-block:: python

       # Getting information about yourself
       print(client.get_me().stringify())

       # Sending a message (you can use 'me' or 'self' to message yourself)
       client.send_message('username', 'Hello World from Telethon!')

       # Sending a file
       client.send_file('username', '/home/myself/Pictures/holidays.jpg')

       # Retrieving messages from a chat
       from telethon import utils
       for message in client.iter_messages('username', limit=10):
           print(utils.get_display_name(message.sender), message.message)

       # Listing all the dialogs (conversations you have open)
       for dialog in client.get_dialogs(limit=10):
           print(utils.get_display_name(dialog.entity), dialog.draft.message)

       # Downloading profile photos (default path is the working directory)
       client.download_profile_photo('username')

       # Once you have a message with .media (if message.media)
       # you can download it using client.download_media():
       messages = client.get_messages('username')
       client.download_media(messages[0])

   **More details**: :ref:`telegram-client`

   See :ref:`telethon-package` for all available friendly methods.


Handling Updates
****************

   .. code-block:: python

       from telethon import events

       # We need to have some worker running
       client.updates.workers = 1

       @client.on(events.NewMessage(incoming=True, pattern='(?i)hi'))
       def handler(event):
           event.reply('Hello!')

       # If you want to handle updates you can't let the script end.
       input('Press enter to exit.')

   **More details**: :ref:`working-with-updates`


----------

You can continue by clicking on the "More details" link below each
snippet of code or the "Next" button at the bottom of the page.
