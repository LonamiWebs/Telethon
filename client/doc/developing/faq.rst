Frequently Asked Questions (FAQ)
================================

.. currentmodule:: telethon

.. contents::


Code without errors doesn't work
--------------------------------

Then it probably has errors, but you haven't enabled logging yet.
To enable logging, at the following code to the top of your main file:

.. code-block:: python

    import logging
    logging.basicConfig(format='[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s',
                        level=logging.WARNING)

Do not wrap your code in ``try / except`` blocks just to hide errors.
It will be a lot more difficult to find what the problem is.
Instead, let Python print the full traceback, or fix the actual error properly.

See the official Python documentation for more information on :mod:`logging`.


My account was deleted/limited when using the library
-----------------------------------------------------

First and foremost, **this is not a problem exclusive to Telethon.
Any third-party library is prone to cause the accounts to appear banned.**
Even official applications can make Telegram ban an account under certain circumstances.
Third-party libraries such as Telethon are a lot easier to use, and as such,
they are misused to spam, which causes Telegram to learn certain patterns and ban suspicious activity.

There is no point in Telethon trying to circumvent this. Even if it succeeded,
spammers would then abuse the library again, and the cycle would repeat.

The library will only do things that you tell it to do.
If you use the library with bad intentions, Telegram will hopefully ban you.

However, you may also be part of a limited country, such as Iran or Russia.
In that case, we have bad news for you. Telegram is much more likely to ban these numbers,
as they are often used to spam other accounts, likely through the use of libraries like this one.
The best advice we can give you is to not abuse the API, like calling many requests really quickly.

We have also had reports from Kazakhstan and China, where connecting would fail.
To solve these connection problems, you should use a proxy (see below).

Telegram may also ban virtual (VoIP) phone numbers, as again, they're likely to be used for spam.

More recently (year 2023 onwards), Telegram has started putting a lot more measures to prevent spam,
with even additions such as anonymous participants in groups or the inability to fetch group members at all.
This means some of the anti-spam measures have gotten more aggressive.

The recommendation has usually been to use the library only on well-established accounts (and not an account you just created),
and to not perform actions that could be seen as abuse.
Telegram decides what those actions are, and they're free to change how they operate at any time.

If you want to check if your account has been limited, simply send a private message to `@SpamBot <https://t.me/SpamBot>`_ through Telegram itself.
You should notice this by getting errors like ``PeerFlood``, which means you're limited,
for instance, when sending a message to some accounts but not others.

For more discussion, please see `issue 297 <https://github.com/LonamiWebs/Telethon/issues/297>`_.


How can I use a proxy?
----------------------

Proxies can be used with Telethon, but they are not directly supported.
If you have problems with Telethon when using a proxy, it will *not* be considered a Telethon bug.

You can use any :mod:`asyncio`-compatible proxy library of your choice, and then define a custom connector:

.. code-block:: python

    from telethon import Client
    # from some_proxy_library import open_proxy_connection

    async def my_proxy_connector(ip, port):
        return await open_proxy_connection(
            host=ip,
            port=port,
            proxy_url='socks5://user:password@127.0.0.1:1080'
        )

    client = Client(..., connector=my_proxy_connector)

For more information, see the :doc:`/concepts/datacenters` concept.


AttributeError: 'coroutine' object has no attribute 'id'
--------------------------------------------------------

Telethon is an asynchronous library, which means you must :keyword:`await` calls that require network access:

.. code-block:: python

    async def handler(event):
        me = await client.get_me()
        #    ^^^^^ note the await
        print(me.id)


sqlite3.OperationalError: database is locked
--------------------------------------------

An older process is still running and is using the same ``'session'`` file.

This error occurs when **two or more clients use the same session**,
that is, when you write the same session name to be used in the client:

* You have an older process using the same session file.
* You have two different scripts running (interactive sessions count too).
* You have two clients in the same script running at the same time.

The solution is, if you need two clients, use two sessions.
If the problem persists and you're on Linux, you can use ``fuser my.session`` to find out the process locking the file.
As a last resort, you can reboot your system.

If you really dislike SQLite, use a different session storage.
See the :doc:`/concepts/sessions` concept to learn more about session storages.


File download is slow or sending files takes too long
-----------------------------------------------------

The communication with Telegram is encrypted.
Encryption requires a lot of math, and doing it in pure Python is very slow.

``cryptg`` is a library which containns the encryption functions used by Telethon.
If it is installed (via ``pip install cryptg``), it will automatically be used and should provide a considerable speed boost.


What does "Task was destroyed but it is pending" mean?
------------------------------------------------------

Your script likely finished abruptly, the :mod:`asyncio` event loop got destroyed,
and the library did not get a chance to properly close the connection and close the session.

Make sure you're either using the context manager for the client (``with client``)
or always call :meth:`~Client.disconnect` before the scripts exits (for example, using ``try / finally``).


Can I use threading with the library?
-------------------------------------

Yes, if you know what you are doing.
However, you will probably have a lot of headaches to get :mod:`threading` threads and :mod:`asyncio` tasks to work together.

If you want to use a threaded library alongside Telethon, like `Flask <flask.pocoo.org/>`_,
consider instead using an asynchronous alternative like `Quart <https://pgjones.gitlab.io/quart/>`_.

If you want to do background work, you probably do not need threads.
See the :mod:`asyncio` documentation to learn how to use tasks and wait on multiple things at the same time.


Telethon gets stuck when used with other async libraries
--------------------------------------------------------

After you call :meth:`Client.connect` (either directly or implicitly via ``with client``),
you cannot change the :mod:`asyncio` event loop from which it's used.

The most common cause is :func:`asyncio.run`, since it creates a new event loop.
If you :func:`asyncio.run` a function to create the client and set it up, you cannot then use a second :func:`asyncio.run` on that client.

Instead, it's often a good idea to have a single ``async def main`` and :func:`asyncio.run` that.
From it, you're also able to call other ``async def`` without having to touch :func:`asyncio.run` again:

.. code-block:: python

    # It's fine to create the client outside as long as you don't connect
    client = Client(...)

    async def main():
        # Now the client will connect, so the loop must not change from now on.
        # But as long as you do all the work inside main, including calling
        # other async functions, things will work.
        async with client:
            ....

    if __name__ == '__main__':
        asyncio.run(main())

Be sure to read the :mod:`asyncio` documentation if you want a better understanding of event loop, tasks, and what functions you can use.


KeyboardInterrupt during handling of asyncio.exceptions.CancelledError
----------------------------------------------------------------------

This is probably not an actual error, but rather the default way most :mod:`asyncio`-based programs exit.
You can verify this running the following code:

.. code-block:: python

    import asyncio

    asyncio.run(asyncio.sleep(86400))

and pressing :kbd:`Control+C` on your keyboard while it's running, which should print something similar to:

.. code-block:: text

    Traceback (most recent call last):
    File ".../Python/Python312/Lib/asyncio/runners.py", line 118, in run
        return self._loop.run_until_complete(task)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    File ".../Python/Python312/Lib/asyncio/base_events.py", line 685, in run_until_complete
        return future.result()
               ^^^^^^^^^^^^^^^
    File ".../Python/Python312/Lib/asyncio/tasks.py", line 665, in sleep
        return await future
               ^^^^^^^^^^^^
    asyncio.exceptions.CancelledError

    During handling of the above exception, another exception occurred:

    Traceback (most recent call last):
    File ".../mycode.py", line 3, in <module>
        asyncio.run(asyncio.sleep(86400))
    File ".../Python/Python312/Lib/asyncio/runners.py", line 194, in run
        return runner.run(main)
               ^^^^^^^^^^^^^^^^
    File ".../Python/Python312/Lib/asyncio/runners.py", line 123, in run
        raise KeyboardInterrupt()
    KeyboardInterrupt

Note how there is a very large error even though Telethon was not involved at all.
When you press :kbd:`Control+C` while Telethon is running, you should see a similar error, as expected.
If you do not want to see this error when stopping your program, wrap the call to :func:`asyncio.run` in a ``try / except``:

.. code-block:: python

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

Telethon does not catch :class:`KeyboardInterrupt` itself to give you the option to handle it in any way you prefer.


Can Telethon also do this thing the official clients do?
--------------------------------------------------------

With the exception of creating accounts, Telethon can do everything an official client can do.

Following the `Pareto principle <https://en.wikipedia.org/wiki/Pareto_principle>`_,
the small curated API Telethon offers aims to cover most common use-cases, but not all of them.
If your use-case is not covered by the :class:`Client` methods, you can instead resort to the :doc:`/concepts/full-api`.

To learn how Telegram Desktop performs a certain request, you can enable what is known as "debug mode".
Different clients may have different ways to enable this feature.

With the Settings screen of Telegram Desktop open, type "debugmode" on your keyboard (without quotes).
This should prompt you to confirm whether you want to enable DEBUG logs.
Confirm, and logging should commence.

With logging enabled, perform the action you want (for example, "delete all messages").
After that, open the text file starting with ``mtp_`` inside Telegram's ``DebugLogs`` folder.
You should find this folder where Telegram is installed (on Windows, ``%AppData%\Telegram Desktop``).

After you're done, you can disable debug mode in the same way you enabled it.
The debug logs may have recorded sensitive information, so be sure to delete them afterwards if you need to.
