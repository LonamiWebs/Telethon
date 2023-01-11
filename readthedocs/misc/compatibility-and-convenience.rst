.. _compatibility-and-convenience:

=============================
Compatibility and Convenience
=============================

Telethon is an `asyncio` library. Compatibility is an important concern,
and while it can't always be kept and mistakes happens, the :ref:`changelog`
is there to tell you when these important changes happen.

.. contents::


Compatibility
=============

Some decisions when developing will inevitable be proven wrong in the future.
One of these decisions was using threads. Now that Python 3.4 is reaching EOL
and using `asyncio` is usable as of Python 3.5 it makes sense for a library
like Telethon to make a good use of it.

If you have old code, **just use old versions** of the library! There is
nothing wrong with that other than not getting new updates or fixes, but
using a fixed version with ``pip install telethon==0.19.1.6`` is easy
enough to do.

You might want to consider using `Virtual Environments
<https://docs.python.org/3/tutorial/venv.html>`_ in your projects.

There's no point in maintaining a synchronous version because the whole point
is that people don't have time to upgrade, and there has been several changes
and clean-ups. Using an older version is the right way to go.

Sometimes, other small decisions are made. These all will be reflected in the
:ref:`changelog` which you should read when upgrading.

If you want to jump the `asyncio` boat, here are some of the things you will
need to start migrating really old code:

.. code-block:: python

    # 1. Import the client from telethon.sync
    from telethon.sync import TelegramClient

    # 2. Change this monster...
    try:
        assert client.connect()
        if not client.is_user_authorized():
            client.send_code_request(phone_number)
            me = client.sign_in(phone_number, input('Enter code: '))

        ...  # REST OF YOUR CODE
    finally:
        client.disconnect()

    # ...for this:
    with client:
        ...  # REST OF YOUR CODE

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


In addition, all the update handlers must be ``async def``, and you need
to ``await`` method calls that rely on network requests, such as getting
the chat or sender. If you don't use updates, you're done!


Convenience
===========

.. note::

    The entire documentation assumes you have done one of the following:

    .. code-block:: python

        from telethon import TelegramClient, sync
        # or
        from telethon.sync import TelegramClient

    This makes the examples shorter and easier to think about.

For quick scripts that don't need updates, it's a lot more convenient to
forget about `asyncio` and just work with sequential code. This can prove
to be a powerful hybrid for running under the Python REPL too.

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
=====

When you're ready to micro-optimize your application, or if you simply
don't need to call any non-basic methods from a synchronous context,
just get rid of ``telethon.sync`` and work inside an ``async def``:

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

    asyncio.run(main())


The ``telethon.sync`` magic module essentially wraps every method behind:

.. code-block:: python

    asyncio.run(main())

With some other tricks, so that you don't have to write it yourself every time.
That's the overhead you pay if you import it, and what you save if you don't.

Learning
========

You know the library uses `asyncio` everywhere, and you want to learn
how to do things right. Even though `asyncio` is its own topic, the
documentation wants you to learn how to use Telethon correctly, and for
that, you need to use `asyncio` correctly too. For this reason, there
is a section called :ref:`mastering-asyncio` that will introduce you to
the `asyncio` world, with links to more resources for learning how to
use it. Feel free to check that section out once you have read the rest.
