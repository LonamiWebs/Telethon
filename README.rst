Telethon
========
.. epigraph::

  ⭐️ Thanks **everyone** who has starred the project, it means a lot!

**Telethon** is Telegram client implementation in **Python 3** which uses
the latest available API of Telegram. Remember to use **pip3** to install!

Installing
----------

.. code:: sh

  pip install telethon


Creating a client
-----------------

.. code:: python

  from telethon import TelegramClient

  # These example values won't work. You must get your own api_id and
  # api_hash from https://my.telegram.org, under API Development.
  api_id = 12345
  api_hash = '0123456789abcdef0123456789abcdef'
  phone = '+34600000000'

  client = TelegramClient('session_name', api_id, api_hash)
  client.connect()

  # If you already have a previous 'session_name.session' file, skip this.
  client.sign_in(phone=phone)
  me = client.sign_in(code=77777)  # Put whatever code you received here.


Doing stuff
-----------

.. code:: python

  print(me.stringify())

  client.send_message('username', 'Hello! Talking to you from Telethon')
  client.send_file('username', '/home/myself/Pictures/holidays.jpg')

  client.download_profile_photo(me)
  total, messages, senders = client.get_message_history('username')
  client.download_media(messages[0])


Next steps
----------

Do you like how Telethon looks? Check the
`wiki over GitHub <https://github.com/LonamiWebs/Telethon/wiki>`_ for a
more in-depth explanation, with examples, troubleshooting issues, and more
useful information.
