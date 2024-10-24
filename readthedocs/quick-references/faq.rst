.. _faq:

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
    logging.basicConfig(format='[%(levelname) %(asctime)s] %(name)s: %(message)s',
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
        await client.send_message(chat, 'Hi')
    except errors.FloodWaitError as e:
        # e.seconds is how many seconds you have
        # to wait before making the request again.
        print('Flood for', e.seconds)


My account was deleted/limited when using the library
=====================================================

First and foremost, **this is not a problem exclusive to Telethon.
Any third-party library is prone to cause the accounts to appear banned.**
Even official applications can make Telegram ban an account under certain
circumstances. Third-party libraries such as Telethon are a lot easier to
use, and as such, they are misused to spam, which causes Telegram to learn
certain patterns and ban suspicious activity.

There is no point in Telethon trying to circumvent this. Even if it succeeded,
spammers would then abuse the library again, and the cycle would repeat.

The library will only do things that you tell it to do. If you use
the library with bad intentions, Telegram will hopefully ban you.

However, you may also be part of a limited country, such as Iran or Russia.
In that case, we have bad news for you. Telegram is much more likely to ban
these numbers, as they are often used to spam other accounts, likely through
the use of libraries like this one. The best advice we can give you is to not
abuse the API, like calling many requests really quickly.

We have also had reports from Kazakhstan and China, where connecting
would fail. To solve these connection problems, you should use a proxy.

Telegram may also ban virtual (VoIP) phone numbers,
as again, they're likely to be used for spam.

More recently (year 2023 onwards), Telegram has started putting a lot more
measures to prevent spam (with even additions such as anonymous participants
in groups or the inability to fetch group members at all). This means some
of the anti-spam measures have gotten more aggressive.

The recommendation has usually been to use the library only on well-established
accounts (and not an account you just created), and to not perform actions that
could be seen as abuse. Telegram decides what those actions are, and they're
free to change how they operate at any time.

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

    me = await client.get_me()
    print(me.username)
    #       ^ we used the dot operator to access the username attribute

    result = await client(functions.photos.GetUserPhotosRequest(
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


event.chat or event.sender is None
==================================

Telegram doesn't always send this information in order to save bandwidth.
If you need the information, you should fetch it yourself, since the library
won't do unnecessary work unless you need to:

.. code-block:: python

    async def handler(event):
        chat = await event.get_chat()
        sender = await event.get_sender()


File download is slow or sending files takes too long
=====================================================

The communication with Telegram is encrypted. Encryption requires a lot of
math, and doing it in pure Python is very slow. ``cryptg`` is a library which
containns the encryption functions used by Telethon. If it is installed (via
``pip install cryptg``), it will automatically be used and should provide
a considerable speed boost. You can know whether it's used by configuring
``logging`` (at ``INFO`` level or lower) *before* importing ``telethon``.

Note that the library does *not* download or upload files in parallel, which
can also help with the speed of downloading or uploading a single file. There
are snippets online implementing that. The reason why this is not built-in
is because the limiting factor in the long run are ``FloodWaitError``, and
using parallel download or uploads only makes them occur sooner.


What does "Server sent a very new message with ID" mean?
========================================================

You may also see this error as "Server sent a very old message with ID".

This is a security feature from Telethon that cannot be disabled and is
meant to protect you against replay attacks.

When this message is incorrectly reported as a "bug",
the most common patterns seem to be:

* Your system time is incorrect.
* The proxy you're using may be interfering somehow.
* The Telethon session is being used or has been used from somewhere else.
  Make sure that you created the session from Telethon, and are not using the
  same session anywhere else. If you need to use the same account from
  multiple places, login and use a different session for each place you need.


What does "Server replied with a wrong session ID" mean?
========================================================

This is a security feature from Telethon that cannot be disabled and is
meant to protect you against unwanted session reuse.

When this message is reported as a "bug", the most common patterns seem to be:

* The proxy you're using may be interfering somehow.
* The Telethon session is being used or has been used from somewhere else.
  Make sure that you created the session from Telethon, and are not using the
  same session anywhere else. If you need to use the same account from
  multiple places, login and use a different session for each place you need.
* You may be using multiple connections to the Telegram server, which seems
  to confuse Telegram.

Most of the time it should be safe to ignore this warning. If the library
still doesn't behave correctly, make sure to check if any of the above bullet
points applies in your case and try to work around it.

If the issue persists and there is a way to reliably reproduce this error,
please add a comment with any additional details you can provide to
`issue 3759`_, and perhaps some additional investigation can be done
(but it's unlikely, as Telegram *is* sending unexpected data).


What does "Could not find a matching Constructor ID for the TLObject" mean?
===========================================================================

Telegram uses "layers", which you can think of as "versions" of the API they
offer. When Telethon reads responses that the Telegram servers send, these
need to be deserialized (into what Telethon calls "TLObjects").

Every Telethon version understands a single Telegram layer. When Telethon
connects to Telegram, both agree on the layer to use. If the layers don't
match, Telegram may send certain objects which Telethon no longer understands.

When this message is reported as a "bug", the most common patterns seem to be
that the Telethon session is being used or has been used from somewhere else.
Make sure that you created the session from Telethon, and are not using the
same session anywhere else. If you need to use the same account from
multiple places, login and use a different session for each place you need.


What does "Task was destroyed but it is pending" mean?
======================================================

Your script likely finished abruptly, the ``asyncio`` event loop got
destroyed, and the library did not get a chance to properly close the
connection and close the session.

Make sure you're either using the context manager for the client or always
call ``await client.disconnect()`` (by e.g. using a ``try/finally``).


What does "The asyncio event loop must not change after connection" mean?
=========================================================================

Telethon uses ``asyncio``, and makes use of things like tasks and queues
internally to manage the connection to the server and match responses to the
requests you make. Most of them are initialized after the client is connected.

For example, if the library expects a result to a request made in loop A, but
you attempt to get that result in loop B, you will very likely find a deadlock.
To avoid a deadlock, the library checks to make sure the loop in use is the
same as the one used to initialize everything, and if not, it throws an error.

The most common cause is ``asyncio.run``, since it creates a new event loop.
If you ``asyncio.run`` a function to create the client and set it up, and then
you ``asyncio.run`` another function to do work, things won't work, so the
library throws an error early to let you know something is wrong.

Instead, it's often a good idea to have a single ``async def main`` and simply
``asyncio.run()`` it and do all the work there. From it, you're also able to
call other ``async def`` without having to touch ``asyncio.run`` again:

.. code-block:: python

    # It's fine to create the client outside as long as you don't connect
    client = TelegramClient(...)

    async def main():
        # Now the client will connect, so the loop must not change from now on.
        # But as long as you do all the work inside main, including calling
        # other async functions, things will work.
        async with client:
            ....

    if __name__ == '__main__':
        asyncio.run(main())

Be sure to read the ``asyncio`` documentation if you want a better
understanding of event loop, tasks, and what functions you can use.


What does "bases ChatGetter" mean?
==================================

In Python, classes can base others. This is called `inheritance
<https://ddg.gg/python%20inheritance>`_. What it means is that
"if a class bases another, you can use the other's methods too".

For example, `Message <telethon.tl.custom.message.Message>` *bases*
`ChatGetter <telethon.tl.custom.chatgetter.ChatGetter>`. In turn,
`ChatGetter <telethon.tl.custom.chatgetter.ChatGetter>` defines
things like `obj.chat_id <telethon.tl.custom.chatgetter.ChatGetter>`.

So if you have a message, you can access that too:

.. code-block:: python

    # ChatGetter has a chat_id property, and Message bases ChatGetter.
    # Thus you can use ChatGetter properties and methods from Message
    print(message.chat_id)


Telegram has a lot to offer, and inheritance helps the library reduce
boilerplate, so it's important to know this concept. For newcomers,
this may be a problem, so we explain what it means here in the FAQ.

Can I send files by ID?
=======================

When people talk about IDs, they often refer to one of two things:
the integer ID inside media, and a random-looking long string.

You cannot use the integer ID to send media. Generally speaking, sending media
requires a combination of ID, ``access_hash`` and ``file_reference``.
The first two are integers, while the last one is a random ``bytes`` sequence.

* The integer ``id`` will always be the same for every account, so every user
  or bot looking at a particular media file, will see a consistent ID.
* The ``access_hash`` will always be the same for a given account, but
  different accounts will each see their own, different ``access_hash``.
  This makes it impossible to get media object from one account and use it in
  another. The other account must fetch the media object itself.
* The ``file_reference`` is random for everyone and will only work for a few
  hours before it expires. It must be refetched before the media can be used
  (to either resend the media or download it).

The second type of "`file ID <https://core.telegram.org/bots/api#inputfile>`_"
people refer to is a concept from the HTTP Bot API. It's a custom format which
encodes enough information to use the media.

Telethon provides an old version of these HTTP Bot API-style file IDs via
``message.file.id``, however, this feature is no longer maintained, so it may
not work. It will be removed in future versions. Nonetheless, it is possible
to find a different Python package (or write your own) to parse these file IDs
and construct the necessary input file objects to send or download the media.


Can I use Flask with the library?
=================================

Yes, if you know what you are doing. However, you will probably have a
lot of headaches to get threads and asyncio to work together. Instead,
consider using `Quart <https://pgjones.gitlab.io/quart/>`_, an asyncio-based
alternative to `Flask <flask.pocoo.org/>`_.

Check out `quart_login.py`_ for an example web-application based on Quart.

Can I use Anaconda/Spyder/IPython with the library?
===================================================

Yes, but these interpreters run the asyncio event loop implicitly,
which interferes with the ``telethon.sync`` magic module.

If you use them, you should **not** import ``sync``:

.. code-block:: python

    # Change any of these...:
    from telethon import TelegramClient, sync, ...
    from telethon.sync import TelegramClient, ...

    # ...with this:
    from telethon import TelegramClient, ...

You are also more likely to get "sqlite3.OperationalError: database is locked"
with them. If they cause too much trouble, just write your code in a ``.py``
file and run that, or use the normal ``python`` interpreter.

.. _logging: https://docs.python.org/3/library/logging.html
.. _@SpamBot: https://t.me/SpamBot
.. _issue 297: https://github.com/LonamiWebs/Telethon/issues/297
.. _issue 3759: https://github.com/LonamiWebs/Telethon/issues/3759
.. _quart_login.py: https://github.com/LonamiWebs/Telethon/tree/v1/telethon_examples#quart_loginpy
