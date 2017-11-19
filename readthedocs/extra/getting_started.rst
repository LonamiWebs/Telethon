.. Telethon documentation master file, created by
   sphinx-quickstart on Fri Nov 17 15:36:11 2017.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.


=================
Getting Started!
=================

Installation
**************

To install Telethon, simply do:

    ``pip install telethon``

If you get something like ``"SyntaxError: invalid syntax"`` or any other error while installing, it's probably because ``pip`` defaults to Python 2, which is not supported. Use ``pip3`` instead.

If you already have the library installed, upgrade with:

    ``pip install --upgrade telethon``.

You can also install the library directly from GitHub or a fork:

   .. code-block:: python

        # pip install git+https://github.com/LonamiWebs/Telethon.git
        or
        $ git clone https://github.com/LonamiWebs/Telethon.git
        $ cd Telethon/
        # pip install -Ue .

If you don't have root access, simply pass the ``--user`` flag to the pip command.




Creating a client
**************
Before working with Telegram's API, you need to get your own API ID and hash:

1. Follow `this link <https://my.telegram.org/>`_ and login with your phone number.

2. Click under API Development tools.

3. A *Create new application* window will appear. Fill in your application details. There is no need to enter any *URL*, and only the first two fields (*App title* and *Short name*) can be changed later as far as I'm aware.

4. Click on *Create application* at the end. Remember that your **API hash is secret** and Telegram won't let you revoke it. Don't post it anywhere!

Once that's ready, the next step is to create a ``TelegramClient``. This class will be your main interface with Telegram's API, and creating one is very simple:

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

**More details**: `Click here <https://github.com/lonamiwebs/telethon/wiki/Creating-a-Client>`_


Simple Stuff
**************
   .. code-block:: python

       print(me.stringify())

       client.send_message('username', 'Hello! Talking to you from Telethon')
       client.send_file('username', '/home/myself/Pictures/holidays.jpg')

       client.download_profile_photo(me)
       total, messages, senders = client.get_message_history('username')
       client.download_media(messages[0])


Diving In
**************

.. note:: More info in our Wiki!

Sending Requests
^^^^^^^^^^^^^^^^^^^^^
    `Here <https://github.com/lonamiwebs/telethon/wiki/Session-Files>`__

Working with updates
^^^^^^^^^^^^^^^^^^^^^
    `Here <https://github.com/lonamiwebs/telethon/wiki/Working-with-Updates>`__

Accessing the full API
^^^^^^^^^^^^^^^^^^^^^^^
    `Here <https://github.com/lonamiwebs/telethon/wiki/Accessing-the-Full-API>`__

