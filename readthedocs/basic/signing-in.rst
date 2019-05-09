.. _signing-in:

==========
Signing In
==========

Before working with Telegram's API, you need to get your own API ID and hash:

1. `Login to your Telegram account <https://my.telegram.org/>`_ with the
   phone number of the developer account to use.

2. Click under API Development tools.

3. A *Create new application* window will appear. Fill in your application
   details. There is no need to enter any *URL*, and only the first two
   fields (*App title* and *Short name*) can currently be changed later.

4. Click on *Create application* at the end. Remember that your
   **API hash is secret** and Telegram won't let you revoke it.
   Don't post it anywhere!

.. note::

    This API ID and hash is the one used by *your application*, not your
    phone number. You can use this API ID and hash with *any* phone number
    or even for bot accounts.


Editing the Code
================

This is a little introduction for those new to Python programming in general.

We will write our code inside ``hello.py``, so you can use any text
editor that you like. To run the code, use ``python3 hello.py`` from
the terminal.

.. important::

    Don't call your script ``telethon.py``! Python will try to import
    the client from there and it will fail with an error such as
    "ImportError: cannot import name 'TelegramClient' ...".


Signing In
==========

We can finally write some code to log into our account!

.. code-block:: python

    from telethon.sync import TelegramClient

    # Use your own values from my.telegram.org
    api_id = 12345
    api_hash = '0123456789abcdef0123456789abcdef'

    # The first parameter is the .session file name (absolute paths allowed)
    with TelegramClient('anon', api_id, api_hash) as client:
        client.send_message('me', 'Hello, myself!')


In the first line, we import the class name so we can create an instance
of the client. Then, we define variables to store our API ID and hash
conveniently.

At last, we create a new `TelegramClient <telethon.client.telegramclient.TelegramClient>`
instance and call it ``client``. We can now use the client variable
for anything that we want, such as sending a message to ourselves.

Using a ``with`` block is the preferred way to use the library. It will
automatically `start() <telethon.client.auth.AuthMethods.start>` the client,
logging or signing up if necessary.

If the ``.session`` file already existed, it will not login
again, so be aware of this if you move or rename the file!


Signing In as a Bot Account
===========================

You can also use Telethon for your bots (normal bot accounts, not users).
You will still need an API ID and hash, but the process is very similar:


.. code-block:: python

    from telethon.sync import TelegramClient

    api_id = 12345
    api_hash = '0123456789abcdef0123456789abcdef'
    bot_token = '12345:0123456789abcdef0123456789abcdef

    # We have to manually call "start" if we want a explicit bot token
    bot = TelegramClient('bot', api_id, api_hash).start(bot_token=bot_token)

    # But then we can use the client instance as usual
    with bot:
        ...


To get a bot account, you need to talk
with `@BotFather <https://t.me/BotFather>`_.


Signing In behind a Proxy
=========================

If you need to use a proxy to access Telegram,
you will need to  `install PySocks`__ and then change:

.. code-block:: python

    TelegramClient('anon', api_id, api_hash)

with

.. code-block:: python

    TelegramClient('anon', api_id, api_hash, proxy=(socks.SOCKS5, '127.0.0.1', 4444))

(of course, replacing the IP and port with the IP and port of the proxye).

The ``proxy=`` argument should be a tuple, a list or a dict,
consisting of parameters described `in PySocks usage`__.

.. __: https://github.com/Anorov/PySocks#installation
.. __: https://github.com/Anorov/PySocks#usage-1
