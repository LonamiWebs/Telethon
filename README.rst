Telethon
========
.. epigraph::

  ⭐️ Thanks **everyone** who has starred the project, it means a lot!

|logo| **Telethon** is an asyncio_ **Python 3**
MTProto_ library to interact with Telegram_'s API
as a user or through a bot account (bot API alternative).

.. important::

    If you have code using Telethon before its 1.0 version, you must
    read `Compatibility and Convenience`_ to learn how to migrate.

What is this?
-------------

Telegram is a popular messaging application. This library is meant
to make it easy for you to write Python programs that can interact
with Telegram. Think of it as a wrapper that has already done the
heavy job for you, so you can focus on developing an application.


Installing
----------

.. code-block:: sh

  pip3 install telethon


Creating a client
-----------------

.. code-block:: python

    import asyncio
    from telethon import TelegramClient, events

    # These example values won't work. You must get your own api_id and
    # api_hash from https://my.telegram.org, under API Development.
    api_id = 12345
    api_hash = '0123456789abcdef0123456789abcdef'

    async def main():
      client = TelegramClient('session_name', api_id, api_hash)
      await client.start()

    asyncio.run(main())


Doing stuff
-----------

.. code-block:: python

    print((await client.get_me()).stringify())

    await client.send_message('username', 'Hello! Talking to you from Telethon')
    await client.send_file('username', '/home/myself/Pictures/holidays.jpg')

    await client.download_profile_photo('me')
    messages = await client.get_messages('username')
    await messages[0].download_media()

    @client.on(events.NewMessage(pattern='(?i)hi|hello'))
    async def handler(event):
        await event.respond('Hey!')


Next steps
----------

Do you like how Telethon looks? Check out `Read The Docs`_ for a more
in-depth explanation, with examples, troubleshooting issues, and more
useful information.

.. _asyncio: https://docs.python.org/3/library/asyncio.html
.. _MTProto: https://core.telegram.org/mtproto
.. _Telegram: https://telegram.org
.. _Compatibility and Convenience: https://docs.telethon.dev/en/stable/misc/compatibility-and-convenience.html
.. _Read The Docs: https://docs.telethon.dev

.. |logo| image:: logo.svg
    :width: 24pt
    :height: 24pt
