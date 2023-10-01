Telethon
========

.. epigraph::

    ⭐️ Thanks **everyone** who has starred the project, it means a lot!

|logo| **Telethon** is an asyncio_ **Python 3**
MTProto_ library to interact with Telegram_'s API
as a user or through a bot account (bot API alternative).

.. important::

    If you have code using Telethon before its 2.0 version, it is strongly
    recommended to read the Migration Guide section in the documentation.
    As with any third-party library for Telegram, be careful not to
    break `Telegram's ToS`_ or `Telegram can ban the account`_.


What is this?
-------------

Telegram is a popular messaging application. This library is meant
to make it easy for you to write Python programs that can interact
with Telegram. Think of it as a wrapper that has already done the
heavy job for you, so you can focus on developing an application.


Installing
----------

.. code-block:: sh

    pip install telethon


Creating a client
-----------------

.. code-block:: python

    from telethon import TelegramClient, events, sync

    # These example values won't work. You must get your own api_id and
    # api_hash from https://my.telegram.org, under API Development.
    api_id = 12345
    api_hash = '0123456789abcdef0123456789abcdef'

    async with TelegramClient('session_name', api_id, api_hash) as client:
        await client.interactive_login()


Doing stuff
-----------

.. code-block:: python

    print(await client.get_me())

    await client.send_message('username', 'Hello! Talking to you from Telethon')
    await client.send_photo('username', '/home/myself/Pictures/holidays.jpg')

    async for message in client.get_messages('username', 1):
        path = await message.download_media()
        print('Saved media to', path)


Next steps
----------

Do you like how Telethon looks? Check out the documentation for a more
in-depth explanation, with examples, troubleshooting issues, and more
useful information.

.. _asyncio: https://docs.python.org/3/library/asyncio.html
.. _MTProto: https://core.telegram.org/mtproto
.. _Telegram: https://telegram.org
.. _Telegram's ToS: https://core.telegram.org/api/terms
.. _Telegram can ban the account: https://docs.telethon.dev/en/stable/quick-references/faq.html#my-account-was-deleted-limited-when-using-the-library

.. |logo| image:: logo.svg
    :width: 24pt
    :height: 24pt
