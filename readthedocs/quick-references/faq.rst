===
FAQ
===

Let's start the quick references section with some useful tips to keep in
mind, with the hope that you will understand why certain things work the
way that they do.

.. contents::


Code without errors doesn't work
================================

Then it probably has errors, but you haven't enabled logging yet.
To enable logging, at the following code to the top of your main file:

.. code-block:: python

    import logging
    logging.basicConfig(format='[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s',
                        level=logging.WARNING)

You can change the logging level to be something different, from less to more information:

.. code-block:: python

    level=logging.CRITICAL  # won't show errors (same as disabled)
    level=logging.ERROR     # will only show errors that you didn't handle
    level=logging.WARNING   # will also show messages with medium severity, such as internal Telegram issues
    level=logging.INFO      # will also show informational messages, such as connection or disconnections
    level=logging.DEBUG     # will show a lot of output to help debugging issues in the library

See the official Python documentation for more information on logging_.


How can I except FloodWaitError?
================================

You can use all errors from the API by importing:

.. code-block:: python

    from telethon import errors

And except them as such:

.. code-block:: python

    try:
        client.send_message(chat, 'Hi')
    except errors.FloodWaitError as e:
        # e.seconds is how many seconds you have
        # to wait before making the request again.
        print('Flood for', e.seconds)


My account was deleted/limited when using the library
=====================================================

The library will only do things that you tell it to do. If you use
the library with bad intentions, Telegram will hopefully ban you.

However, you may also be part of a limited country, such as Iran or Russia.
In that case, we have bad news for you. Telegram is much more likely to ban
these numbers, as they are often used to spam other accounts, likely through
the use of libraries like this one. The best advice we can give you is to not
abuse the API, like calling many requests really quickly, and to sign up with
these phones through an official application.

We have also had reports from Kazakhstan and China, where connecting
would fail. To solve these connection problems, you should use a proxy.

Telegram may also ban virtual (VoIP) phone numbers,
as again, they're likely to be used for spam.

If you want to check if your account has been limited,
simply send a private message to `@SpamBot`_ through Telegram itself.
You should notice this by getting errors like ``PeerFloodError``,
which means you're limited, for instance,
when sending a message to some accounts but not others.

For more discussion, please see `issue 297`_.


How can I use a proxy?
======================

This was one of the first things described in :ref:`signing-in`.


How do I access a field?
========================

This is basic Python knowledge. You should use the dot operator:

.. code-block:: python

    me = client.get_me()
    print(me.username)
    #       ^ we used the dot operator to access the username attribute

    result = client(functions.photos.GetUserPhotosRequest(
        user_id='me',
        offset=0,
        max_id=0,
        limit=100
    ))

    # Working with list is also pretty basic
    print(result.photos[0].sizes[-1].type)
    #           ^       ^ ^       ^ ^
    #           |       | |       | \ type
    #           |       | |       \ last size
    #           |       | \ list of sizes
    #  access   |       \ first photo from the list
    #  the...   \ list of photos
    #
    # To print all, you could do (or mix-and-match):
    for photo in result.photos:
        for size in photo.sizes:
            print(size.type)


AttributeError: 'coroutine' object has no attribute 'id'
========================================================

You either forgot to:

.. code-block:: python

    import telethon.sync
    #              ^^^^^ import sync

Or:

.. code-block:: python

    async def handler(event):
        me = await client.get_me()
        #    ^^^^^ note the await
        print(me.username)

This error happens frequently when trying to run Telethon-enabled code inside a Python environment like Anaconda/Spyder. Try running the code in a normal commandline instead.

sqlite3.OperationalError: database is locked
============================================

An older process is still running and is using the same ``'session'`` file.

This error occurs when **two or more clients use the same session**,
that is, when you write the same session name to be used in the client:

* You have an older process using the same session file.
* You have two different scripts running (interactive sessions count too).
* You have two clients in the same script running at the same time.

The solution is, if you need two clients, use two sessions. If the
problem persists and you're on Linux, you can use ``fuser my.session``
to find out the process locking the file. As a last resort, you can
reboot your system.

If you really dislike SQLite, use a different session storage. There
is an entire section covering that at :ref:`sessions`.

This error also happens frequently when trying to run Telethon-enabled code inside a Python environment like Anaconda/Spyder. Try running the code in a normal commandline instead.

event.chat or event.sender is None
==================================

Telegram doesn't always send this information in order to save bandwidth.
If you need the information, you should fetch it yourself, since the library
won't do unnecessary work unless you need to:

.. code-block:: python

    async def handler(event):
        chat = await event.get_chat()
        sender = await event.get_sender()


Can I use Flask with the library?
=================================

Yes, if you know what you are doing. However, you will probably have a
lot of headaches to get threads and asyncio to work together. Instead,
consider using `Quart <https://pgjones.gitlab.io/quart/>`_, an asyncio-based
alternative to `Flask <flask.pocoo.org/>`_.

.. _logging: https://docs.python.org/3/library/logging.html
.. _@SpamBot: https://t.me/SpamBot
.. _issue 297: https://github.com/LonamiWebs/Telethon/issues/297
