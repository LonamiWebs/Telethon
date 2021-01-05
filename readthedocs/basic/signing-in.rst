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

    from telethon import TelegramClient

    # Use your own values from my.telegram.org
    api_id = 12345
    api_hash = '0123456789abcdef0123456789abcdef'

    # The first parameter is the .session file name (absolute paths allowed)
    with TelegramClient('anon', api_id, api_hash) as client:
        client.loop.run_until_complete(client.send_message('me', 'Hello, myself!'))


In the first line, we import the class name so we can create an instance
of the client. Then, we define variables to store our API ID and hash
conveniently.

At last, we create a new `TelegramClient <telethon.client.telegramclient.TelegramClient>`
instance and call it ``client``. We can now use the client variable
for anything that we want, such as sending a message to ourselves.

.. note::

    Since Telethon is an asynchronous library, you need to ``await``
    coroutine functions to have them run (or otherwise, run the loop
    until they are complete). In this tiny example, we don't bother
    making an ``async def main()``.

    See :ref:`mastering-asyncio` to find out more.


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
    bot_token = '12345:0123456789abcdef0123456789abcdef'

    # We have to manually call "start" if we want an explicit bot token
    bot = TelegramClient('bot', api_id, api_hash).start(bot_token=bot_token)

    # But then we can use the client instance as usual
    with bot:
        ...


To get a bot account, you need to talk
with `@BotFather <https://t.me/BotFather>`_.


Signing In behind a Proxy
=========================

If you need to use a proxy to access Telegram,
you will need to either:

* For Python >= 3.6 : `install python-socks[asyncio]`__
* For Python <= 3.5 : `install PySocks`__

and then change

.. code-block:: python

    TelegramClient('anon', api_id, api_hash)

with

.. code-block:: python

    TelegramClient('anon', api_id, api_hash, proxy=("socks5", '127.0.0.1', 4444))

(of course, replacing the protocol, IP and port with the protocol, IP and port of the proxy).

The ``proxy=`` argument should be a dict (or tuple, for backwards compatibility),
consisting of parameters described `in PySocks usage`__.

The allowed values for the argument ``proxy_type`` are:

* For Python <= 3.5:
    * ``socks.SOCKS5`` or ``'socks5'``
    * ``socks.SOCKS4`` or ``'socks4'``
    * ``socks.HTTP`` or ``'http'``

* For Python >= 3.6:
    * All of the above
    * ``python_socks.SOCKS5``
    * ``python_socks.SOCKS4``
    * ``python_socks.HTTP``


Example:

.. code-block:: python

    proxy = {
        'proxy_type': 'socks5', # (mandatory) protocol to use (see above)
        'addr': '1.1.1.1',      # (mandatory) proxy IP address
        'port': 5555,           # (mandatory) proxy port number
        'username': 'foo',      # (optional) username if the proxy requires auth
        'password': 'bar',      # (optional) password if the proxy requires auth
        'rdns': True            # (optional) whether to use remote or local resolve, default remote
    }

For backwards compatibility with ``PySocks`` the following format
is possible (but discouraged):

.. code-block:: python

    proxy = (socks.SOCKS5, '1.1.1.1', 5555, True, 'foo', 'bar')

.. __: https://github.com/romis2012/python-socks#installation
.. __: https://github.com/Anorov/PySocks#installation
.. __: https://github.com/Anorov/PySocks#usage-1


Using MTProto Proxies
=====================

MTProto Proxies are Telegram's alternative to normal proxies,
and work a bit differently. The following protocols are available:

* ``ConnectionTcpMTProxyAbridged``
* ``ConnectionTcpMTProxyIntermediate``
* ``ConnectionTcpMTProxyRandomizedIntermediate`` (preferred)

For now, you need to manually specify these special connection modes
if you want to use a MTProto Proxy. Your code would look like this:

.. code-block:: python

    from telethon import TelegramClient, connection
    #   we need to change the connection ^^^^^^^^^^

    client = TelegramClient(
        'anon',
        api_id,
        api_hash,

        # Use one of the available connection modes.
        # Normally, this one works with most proxies.
        connection=connection.ConnectionTcpMTProxyRandomizedIntermediate,

        # Then, pass the proxy details as a tuple:
        #     (host name, port, proxy secret)
        #
        # If the proxy has no secret, the secret must be:
        #     '00000000000000000000000000000000'
        proxy=('mtproxy.example.com', 2002, 'secret')
    )

In future updates, we may make it easier to use MTProto Proxies
(such as avoiding the need to manually pass ``connection=``).

In short, the same code above but without comments to make it clearer:

.. code-block:: python

    from telethon import TelegramClient, connection

    client = TelegramClient(
        'anon', api_id, api_hash,
        connection=connection.ConnectionTcpMTProxyRandomizedIntermediate,
        proxy=('mtproxy.example.com', 2002, 'secret')
    )
