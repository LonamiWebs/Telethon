===========
Quick-Start
===========

Let's see a longer example to learn some of the methods that the library
has to offer. These are known as "friendly methods", and you should always
use these if possible.

.. code-block:: python

    from telethon.sync import TelegramClient

    # Remember to use your own values from my.telegram.org!
    api_id = 12345
    api_hash = '0123456789abcdef0123456789abcdef'

    with TelegramClient('anon', api_id, api_hash) as client:
        # Getting information about yourself
        me = client.get_me()

        # "me" is an User object. You can pretty-print
        # any Telegram object with the "stringify" method:
        print(me.stringify())

        # When you print something, you see a representation of it.
        # You can access all attributes of Telegram objects with
        # the dot operator. For example, to get the username:
        username = me.username
        print(username)
        print(me.phone)

        # You can print all the dialogs/conversations that you are part of:
        for dialog in client.iter_dialogs():
            print(dialog.name, 'has ID', dialog.id)

        # You can send messages to yourself...
        client.send_message('me', 'Hello, myself!')
        # ...to some chat ID
        client.send_message(-100123456, 'Hello, group!')
        # ...to your contacts
        client.send_message('+34600123123', 'Hello, friend!')
        # ...or even to any username
        client.send_message('TelethonChat', 'Hello, Telethon!')

        # You can, of course, use markdown in your messages:
        message = client.send_message(
            'me',
            'This message has **bold**, `code`, __italics__ and '
            'a [nice website](https://lonamiwebs.github.io)!',
            link_preview=False
        )

        # Sending a message returns the sent message object, which you can use
        print(message.raw_text)

        # You can reply to messages directly if you have a message object
        message.reply('Cool!')

        # Or send files, songs, documents, albums...
        client.send_file('me', '/home/me/Pictures/holidays.jpg')

        # You can print the message history of any chat:
        for message in client.iter_messages('me'):
            print(message.id, message.text)

            # You can download media from messages, too!
            # The method will return the path where the file was saved.
            if message.photo:
                path = message.download_media()
                print('File saved to', path)


Here, we show how to sign in, get information about yourself, send
messages, files, getting chats, printing messages, and downloading
files.

You should make sure that you understand what the code shown here
does, take note on how methods are called and used and so on before
proceeding. We will see all the available methods later on.
