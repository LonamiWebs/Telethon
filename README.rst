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

    from telethon import TelegramClient, events, sync

    # These example values won't work. You must get your own api_id and
    # api_hash from https://my.telegram.org, under API Development.
    api_id = 12345
    api_hash = '0123456789abcdef0123456789abcdef'

    client = TelegramClient('session_name', api_id, api_hash)
    client.start()


Doing stuff
-----------

.. code-block:: python

    print(client.get_me().stringify())

    client.send_message('username', 'Hello! Talking to you from Telethon')
    client.send_file('username', '/home/myself/Pictures/holidays.jpg')

    client.download_profile_photo('me')
    messages = client.get_messages('username')
    messages[0].download_media()

    @client.on(events.NewMessage(pattern='(?i)hi|hello'))
    async def handler(event):
        await event.respond('Hey!')

our official groups
----------

Join `the main chat`_

Join `the offtopic chat`_

Group for `country-limited accounts like Iran`_

Join `LonamiWebs general talk`_

Next steps
----------

Do you like how Telethon looks? Check out `Read The Docs`_ for a more
in-depth explanation, with examples, troubleshooting issues, and more
useful information.

.. _asyncio: https://docs.python.org/3/library/asyncio.html
.. _MTProto: https://core.telegram.org/mtproto
.. _Telegram: https://telegram.org
.. _Compatibility and Convenience: https://telethon.readthedocs.io/en/latest/extra/basic/compatibility-and-convenience.html
.. _the main chat: http://t.me/TelethonChat
.. _the offtopic chat: http://t.me/TelethonOfftopic
.. _country-limited accounts like Iran: http://t.me/joinchat/ENIGn1OHKk074GGhkGR0Kg
.. _LonamiWebs general talk: http://t.me/LonamiWebs
.. _Read The Docs: https://telethon.readthedocs.io

.. |logo| image:: logo.svg
    :width: 24pt
    :height: 24pt
