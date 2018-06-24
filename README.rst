Telethon
========
.. epigraph::

  ⭐️ Thanks **everyone** who has starred the project, it means a lot!

|logo| **Telethon** is an `asyncio
<https://docs.python.org/3/library/asyncio.html>`_ **Python 3** library
to interact with Telegram's API.

If you don't like ``asyncio``, you can still use `a simpler version
<https://github.com/LonamiWebs/Telethon/tree/sync>`_ that uses threads instead.


What is this?
-------------

Telegram is a popular messaging application. This library is meant
to make it easy for you to write Python programs that can interact
with Telegram. Think of it as a wrapper that has already done the
heavy job for you, so you can focus on developing an application.


Installing
----------

.. code:: sh

  pip3 install telethon-aio


Creating a client
-----------------

.. code:: python

    import asyncio
    loop = asyncio.get_event_loop()

    from telethon import TelegramClient

    # These example values won't work. You must get your own api_id and
    # api_hash from https://my.telegram.org, under API Development.
    api_id = 12345
    api_hash = '0123456789abcdef0123456789abcdef'

    client = TelegramClient('session_name', api_id, api_hash)
    loop.run_until_complete(client.start())


Doing stuff
-----------

.. code:: python

    async def main():
        me = await client.get_me()
        print(me.stringify())

        await client.send_message('username', 'Hello! Talking to you from Telethon')
        await client.send_file('username', '/home/myself/Pictures/holidays.jpg')

        await client.download_profile_photo('me')
        messages = await client.get_messages('username')
        await messages[0].download_media()

    loop.run_until_complete(main())


Next steps
----------

Do you like how Telethon looks? Check out `Read The Docs
<http://telethon.rtfd.io/>`_ for a more in-depth explanation,
with examples, troubleshooting issues, and more useful information.


.. |logo| image:: logo.svg
    :width: 24pt
    :height: 24pt
