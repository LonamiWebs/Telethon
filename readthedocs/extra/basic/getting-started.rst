.. _getting-started:


===============
Getting Started
===============

.. contents::


Simple Installation
*******************

.. code-block:: sh

    pip3 install telethon

**More details**: :ref:`installation`


Creating a client
*****************

.. code-block:: python

    from telethon import TelegramClient, sync

    # These example values won't work. You must get your own api_id and
    # api_hash from https://my.telegram.org, under API Development.
    api_id = 12345
    api_hash = '0123456789abcdef0123456789abcdef'

    client = TelegramClient('session_name', api_id, api_hash).start()

**More details**: :ref:`creating-a-client`


Basic Usage
***********

.. code-block:: python

    # Getting information about yourself
    me = client.get_me()
    print(me.stringify())

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
        print(dialog.name, dialog.draft.text)

    # Downloading profile photos (default path is the working directory)
    client.download_profile_photo('username')

    # Once you have a message with .media (if message.media)
    # you can download it using client.download_media(),
    # or even using message.download_media():
    messages = client.get_messages('username')
    messages[0].download_media()

**More details**: :ref:`telegram-client`

See :ref:`telethon-client` for all available friendly methods.


Handling Updates
****************

.. code-block:: python

    from telethon import events

    @client.on(events.NewMessage(incoming=True, pattern='(?i)hi'))
    async def handler(event):
        await event.reply('Hello!')

    client.run_until_disconnected()

**More details**: :ref:`working-with-updates`


----------

You can continue by clicking on the "More details" link below each
snippet of code or the "Next" button at the bottom of the page.
