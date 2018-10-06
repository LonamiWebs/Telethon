.. _compatibility-and-convenience:

=============================
Compatibility and Convenience
=============================

Telethon is an ``asyncio`` library. Compatibility is an important concern,
and while it can't always be kept and mistakes happens, the :ref:`changelog`
is there to tell you when these important changes happen.

.. contents::


Compatibility
*************

.. important::

    **You should not enable the thread-compatibility mode for new projects.**
    It comes with a cost, and new projects will greatly benefit from using
    ``asyncio`` by default such as increased speed and easier reasoning about
    the code flow. You should only enable it for old projects you don't have
    the time to upgrade to ``asyncio``.

There exists a fair amount of code online using Telethon before it reached
its 1.0 version, where it became fully asynchronous by default. Since it was
necessary to clean some things, compatibility was not kept 100% but the
changes are simple:

.. code-block:: python

    # 1. The library no longer uses threads.
    # Add this at the **beginning** of your script to work around that.
    from telethon import full_sync
    full_sync.enable()

    # 2. client.connect() no longer returns True.
    # Change this...
    assert client.connect()
    # ...for this:
    client.connect()

    # 3. client.idle() no longer exists.
    # Change this...
    client.idle()
    # ...to this:
    client.run_until_disconnected()

    # 4. client.add_update_handler no longer exists.
    # Change this...
    client.add_update_handler(handler)
    # ...to this:
    client.add_event_handler(handler)

    # 5. It's good practice to stop the full_sync mode once you're done
    try:
        ...  # all your code in here
    finally:
        full_sync.stop()


Convenience
***********

.. note::

    The entire documentation assumes you have done one of the following:

    .. code-block:: python

        from telethon import TelegramClient, sync
        # or
        from telethon.sync import TelegramClient

    This makes the examples shorter and easier to think about.

For quick scripts that don't need updates, it's a lot more convenient to
forget about ``full_sync`` or ``asyncio`` and just work with sequential code.
This can prove to be a powerful hybrid for running under the Python REPL too.

.. code-block:: python

    from telethon.sync import TelegramClient
    #            ^~~~~ note this part; it will manage the asyncio loop for you

    with TelegramClient(...) as client:
        print(client.get_me().username)
        #     ^ notice the lack of await, or loop.run_until_complete().
        #       Since there is no loop running, this is done behind the scenes.
        #
        message = client.send_message('me', 'Hi!')
        import time
        time.sleep(5)
        message.delete()

        # You can also have an hybrid between a synchronous
        # part and asynchronous event handlers.
        #
        from telethon import events
        @client.on(events.NewMessage(pattern='(?i)hi|hello'))
        async def handler(event):
            await event.reply('hey')

        client.run_until_disconnected()


Some methods, such as ``with``, ``start``, ``disconnect`` and
``run_until_disconnected`` work both in synchronous and asynchronous
contexts by default for convenience, and to avoid the little overhead
it has when using methods like sending a message, getting messages, etc.
This keeps the best of both worlds as a sane default.

.. note::

    As a rule of thumb, if you're inside an ``async def`` and you need
    the client, you need to ``await`` calls to the API. If you call other
    functions that also need API calls, make them ``async def`` and ``await``
    them too. Otherwise, there is no need to do so with this mode.

Speed
*****

When you're ready to micro-optimize your application, or if you simply
don't need to call any non-basic methods from a synchronous context,
just get rid of both ``telethon.sync`` and ``telethon.full_sync``:

.. code-block:: python

    import asyncio
    from telethon import TelegramClient, events

    async def main():
        async with TelegramClient(...) as client:
            print((await client.get_me()).username)
            #     ^_____________________^ notice these parenthesis
            #     You want to ``await`` the call, not the username.
            #
            message = await client.send_message('me', 'Hi!')
            await asyncio.sleep(5)
            await message.delete()

            @client.on(events.NewMessage(pattern='(?i)hi|hello'))
            async def handler(event):
                await event.reply('hey')

            await client.run_until_disconnected()

    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())


The ``telethon.sync`` magic module simply wraps every method behind:

.. code-block:: python

    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())

So that you don't have to write it yourself every time. That's the
overhead you pay if you import it, and what you save if you don't.

Learning
********

You know the library uses ``asyncio`` everywhere, and you want to learn
how to do things right. Even though ``asyncio`` is its own topic, the
documentation wants you to learn how to use Telethon correctly, and for
that, you need to use ``asyncio`` correctly too. For this reason, there
is a section called :ref:`mastering-asyncio` that will introduce you to
the ``asyncio`` world, with links to more resources for learning how to
use it. Feel free to check that section out once you have read the rest.
