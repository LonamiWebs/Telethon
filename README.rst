Telethon
========
.. epigraph::

    This is the ``asyncio`` version of the library. If you don't know how
    to work with it, `see here https://pypi.python.org/pypi/Telethon`__.

**Telethon** is Telegram client implementation in **Python 3** which uses
the latest available API of Telegram.


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

.. warning::

  Be careful **not** to install ``telethon-asyncio`` or other
  variants, someone else name-squatted those and are unofficial!


Creating a client
-----------------

.. code:: python

  import asyncio
  from telethon import TelegramClient

  # These example values won't work. You must get your own api_id and
  # api_hash from https://my.telegram.org, under API Development.
  api_id = 12345
  api_hash = '0123456789abcdef0123456789abcdef'

  client = TelegramClient('session_name', api_id, api_hash)
  async def main():
      await client.start()

  asyncio.get_event_loop().run_until_complete(main())

Doing stuff
-----------

Note that this assumes you're inside an "async def" method. Check out the
`Python documentation <https://docs.python.org/3/library/asyncio-dev.html>`_
if you're new with ``asyncio``.

.. code:: python

  print((await client.get_me()).stringify())

  await client.send_message('username', 'Hello! Talking to you from Telethon')
  await client.send_file('username', '/home/myself/Pictures/holidays.jpg')

  await client.download_profile_photo('me')
  messages = await client.get_messages('username')
  await client.download_media(messages[0])


Next steps
----------

Do you like how Telethon looks? Check out
`Read The Docs <http://telethon.rtfd.io/>`_
for a more in-depth explanation, with examples, troubleshooting issues,
and more useful information. Note that the examples there are written for
the threaded version, not the one using asyncio. However, you just need to
await every remote call.
