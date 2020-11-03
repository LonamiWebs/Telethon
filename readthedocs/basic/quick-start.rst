===========
Quick-Start
===========

Let's see a longer example to learn some of the methods that the library
has to offer. These are known as "friendly methods", and you should always
use these if possible.

.. code-block:: python

    from telethon import TelegramClient

    # Remember to use your own values from my.telegram.org!
    api_id = 12345
    api_hash = '0123456789abcdef0123456789abcdef'
    client = TelegramClient('anon', api_id, api_hash)

    async def main():
        # Getting information about yourself
        me = await client.get_me()

        # "me" is a user object. You can pretty-print
        # any Telegram object with the "stringify" method:
        print(me.stringify())

        # When you print something, you see a representation of it.
        # You can access all attributes of Telegram objects with
        # the dot operator. For example, to get the username:
        username = me.username
        print(username)
        print(me.phone)

        # You can print all the dialogs/conversations that you are part of:
        async for dialog in client.iter_dialogs():
            print(dialog.name, 'has ID', dialog.id)

        # You can send messages to yourself...
        await client.send_message('me', 'Hello, myself!')
        # ...to some chat ID
        await client.send_message(-100123456, 'Hello, group!')
        # ...to your contacts
        await client.send_message('+34600123123', 'Hello, friend!')
        # ...or even to any username
        await client.send_message('username', 'Testing Telethon!')

        # You can, of course, use markdown in your messages:
        message = await client.send_message(
            'me',
            'This message has **bold**, `code`, __italics__ and '
            'a [nice website](https://example.com)!',
            link_preview=False
        )

        # Sending a message returns the sent message object, which you can use
        print(message.raw_text)

        # You can reply to messages directly if you have a message object
        await message.reply('Cool!')

        # Or send files, songs, documents, albums...
        await client.send_file('me', '/home/me/Pictures/holidays.jpg')

        # You can print the message history of any chat:
        async for message in client.iter_messages('me'):
            print(message.id, message.text)

            # You can download media from messages, too!
            # The method will return the path where the file was saved.
            if message.photo:
                path = await message.download_media()
                print('File saved to', path)  # printed after download is done

    with client:
        client.loop.run_until_complete(main())


Here, we show how to sign in, get information about yourself, send
messages, files, getting chats, printing messages, and downloading
files.

You should make sure that you understand what the code shown here
does, take note on how methods are called and used and so on before
proceeding. We will see all the available methods later on.

.. important::

    Note that Telethon is an asynchronous library, and as such, you should
    get used to it and learn a bit of basic `asyncio`. This will help a lot.
    As a quick start, this means you generally want to write all your code
    inside some ``async def`` like so:

    .. code-block:: python

        client = ...

        async def do_something(me):
            ...

        async def main():
            # Most of your code should go here.
            # You can of course make and use your own async def (do_something).
            # They only need to be async if they need to await things.
            me = await client.get_me()
            await do_something(me)

        with client:
            client.loop.run_until_complete(main())

    After you understand this, you may use the ``telethon.sync`` hack if you
    want do so (see :ref:`compatibility-and-convenience`), but note you may
    run into other issues (iPython, Anaconda, etc. have some issues with it).
