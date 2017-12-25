.. Telethon documentation master file, created by
   sphinx-quickstart on Fri Nov 17 15:36:11 2017.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.


=================
Getting Started!
=================

Simple Installation
*********************

   ``pip install telethon``

   **More details**: :ref:`installation`


Creating a client
**************

   .. code-block:: python

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

   **More details**: :ref:`creating-a-client`


Simple Stuff
**************
   .. code-block:: python

       print(me.stringify())

       client.send_message('username', 'Hello! Talking to you from Telethon')
       client.send_file('username', '/home/myself/Pictures/holidays.jpg')

       client.download_profile_photo(me)
       total, messages, senders = client.get_message_history('username')
       client.download_media(messages[0])

