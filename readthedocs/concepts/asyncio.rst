.. _mastering-asyncio:

=================
Mastering asyncio
=================

.. contents::


What's asyncio?
===============

`asyncio` is a Python 3's built-in library. This means it's already installed if
you have Python 3. Since Python 3.5, it is convenient to work with asynchronous
code. Before (Python 3.4) we didn't have ``async`` or ``await``, but now we do.

`asyncio` stands for *Asynchronous Input Output*. This is a very powerful
concept to use whenever you work IO. Interacting with the web or external
APIs such as Telegram's makes a lot of sense this way.


Why asyncio?
============

Asynchronous IO makes a lot of sense in a library like Telethon.
You send a request to the server (such as "get some message"), and
thanks to `asyncio`, your code won't block while a response arrives.

The alternative would be to spawn a thread for each update so that
other code can run while the response arrives. That is *a lot* more
expensive.

The code will also run faster, because instead of switching back and
forth between the OS and your script, your script can handle it all.
Avoiding switching saves quite a bit of time, in Python or any other
language that supports asynchronous IO. It will also be cheaper,
because tasks are smaller than threads, which are smaller than processes.


What are asyncio basics?
========================

The code samples below assume that you have Python 3.7 or greater installed.

.. code-block:: python

    # First we need the asyncio library
    import asyncio

    # We also need something to run
    async def main():
        for char in 'Hello, world!\n':
            print(char, end='', flush=True)
            await asyncio.sleep(0.2)

    # Then, we can create a new asyncio loop and use it to run our coroutine.
    # The creation and tear-down of the loop is hidden away from us.
    asyncio.run(main())


What does telethon.sync do?
===========================

The moment you import any of these:

.. code-block:: python

    from telethon import sync, ...
    # or
    from telethon.sync import ...
    # or
    import telethon.sync

The ``sync`` module rewrites most ``async def``
methods in Telethon to something similar to this:

.. code-block:: python

    def new_method():
        result = original_method()
        if loop.is_running():
            # the loop is already running, return the await-able to the user
            return result
        else:
            # the loop is not running yet, so we can run it for the user
            return loop.run_until_complete(result)


That means you can do this:

.. code-block:: python

    print(client.get_me().username)

Instead of this:

.. code-block:: python

    me = client.loop.run_until_complete(client.get_me())
    print(me.username)

    # or, using asyncio's default loop (it's the same)
    import asyncio
    loop = asyncio.get_running_loop()  # == client.loop
    me = loop.run_until_complete(client.get_me())
    print(me.username)


As you can see, it's a lot of boilerplate and noise having to type
``run_until_complete`` all the time, so you can let the magic module
to rewrite it for you. But notice the comment above: it won't run
the loop if it's already running, because it can't. That means this:

.. code-block:: python

    async def main():
        # 3. the loop is running here
        print(
            client.get_me()  # 4. this will return a coroutine!
            .username  # 5. this fails, coroutines don't have usernames
        )

    loop.run_until_complete(  # 2. run the loop and the ``main()`` coroutine
        main()  # 1. calling ``async def`` "returns" a coroutine
    )


Will fail. So if you're inside an ``async def``, then the loop is
running, and if the loop is running, you must ``await`` things yourself:

.. code-block:: python

    async def main():
        print((await client.get_me()).username)

    loop.run_until_complete(main())


What are async, await and coroutines?
=====================================

The ``async`` keyword lets you define asynchronous functions,
also known as coroutines, and also iterate over asynchronous
loops or use ``async with``:

.. code-block:: python

    import asyncio

    async def main():
        # ^ this declares the main() coroutine function

        async with client:
            # ^ this is an asynchronous with block

            async for message in client.iter_messages(chat):
                # ^ this is a for loop over an asynchronous generator

                print(message.sender.username)

    asyncio.run(main())
    # ^ this will create a new asyncio loop behind the scenes and tear it down
    #   once the function returns. It will run the loop untiil main finishes.
    #   You should only use this function if there is no other loop running.


The ``await`` keyword blocks the *current* task, and the loop can run
other tasks. Tasks can be thought of as "threads", since many can run
concurrently:

.. code-block:: python

    import asyncio

    async def hello(delay):
        await asyncio.sleep(delay)  # await tells the loop this task is "busy"
        print('hello')  # eventually the loop resumes the code here

    async def world(delay):
        # the loop decides this method should run first
        await asyncio.sleep(delay)  # await tells the loop this task is "busy"
        print('world')  # eventually the loop finishes all tasks

    async def main():
        asyncio.create_task(world(2))  # create the world task, passing 2 as delay
        asyncio.create_task(hello(delay=1))  # another task, but with delay 1
        await asyncio.sleep(3)  # wait for three seconds before exiting

    try:
        # create a new temporary asyncio loop and use it to run main
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

The same example, but without the comment noise:

.. code-block:: python

    import asyncio

    async def hello(delay):
        await asyncio.sleep(delay)
        print('hello')

    async def world(delay):
        await asyncio.sleep(delay)
        print('world')

    async def main():
        asyncio.create_task(world(2))
        asyncio.create_task(hello(delay=1))
        await asyncio.sleep(3)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass


Can I use threads?
==================

Yes, you can, but you must understand that the loops themselves are
not thread safe. and you must be sure to know what is happening. The
easiest and cleanest option is to use `asyncio.run` to create and manage
the new event loop for you:

.. code-block:: python

    import asyncio
    import threading

    async def actual_work():
        client = TelegramClient(..., loop=loop)
        ...  # can use `await` here

    def go():
        asyncio.run(actual_work())

    threading.Thread(target=go).start()


Generally, **you don't need threads** unless you know what you're doing.
Just create another task, as shown above. If you're using the Telethon
with a library that uses threads, you must be careful to use `threading.Lock`
whenever you use the client, or enable the compatible mode. For that, see
:ref:`compatibility-and-convenience`.

You may have seen this error:

.. code-block:: text

    RuntimeError: There is no current event loop in thread 'Thread-1'.

It just means you didn't create a loop for that thread. Please refer to
the ``asyncio`` documentation to correctly learn how to set the event loop
for non-main threads.


client.run_until_disconnected() blocks!
=======================================

All of what `client.run_until_disconnected()
<telethon.client.updates.UpdateMethods.run_until_disconnected>` does is
run the `asyncio`'s event loop until the client is disconnected. That means
*the loop is running*. And if the loop is running, it will run all the tasks
in it. So if you want to run *other* code, create tasks for it:

.. code-block:: python

    from datetime import datetime

    async def clock():
        while True:
            print('The time:', datetime.now())
            await asyncio.sleep(1)

    loop.create_task(clock())
    ...
    client.run_until_disconnected()

This creates a task for a clock that prints the time every second.
You don't need to use `client.run_until_disconnected()
<telethon.client.updates.UpdateMethods.run_until_disconnected>` either!
You just need to make the loop is running, somehow. `loop.run_forever()
<asyncio.loop.run_forever()>` and `loop.run_until_complete()
<asyncio.loop.run_until_complete>` can also be used to run
the loop, and Telethon will be happy with any approach.

Of course, there are better tools to run code hourly or daily, see below.


What else can asyncio do?
=========================

Asynchronous IO is a really powerful tool, as we've seen. There are plenty
of other useful libraries that also use `asyncio` and that you can integrate
with Telethon.

* `aiohttp <https://github.com/aio-libs/aiohttp>`_ is like the infamous
  `requests <https://github.com/requests/requests/>`_ but asynchronous.
* `quart <https://gitlab.com/pgjones/quart>`_ is an asynchronous alternative
  to `Flask <http://flask.pocoo.org/>`_.
* `aiocron <https://github.com/gawel/aiocron>`_ lets you schedule things
  to run things at a desired time, or run some tasks hourly, daily, etc.

And of course, `asyncio <https://docs.python.org/3/library/asyncio.html>`_
itself! It has a lot of methods that let you do nice things. For example,
you can run requests in parallel:

.. code-block:: python

    async def main():
        last, sent, download_path = await asyncio.gather(
            client.get_messages('telegram', 10),
            client.send_message('me', 'Using asyncio!'),
            client.download_profile_photo('telegram')
        )

    loop.run_until_complete(main())


This code will get the 10 last messages from `@telegram
<https://t.me/telegram>`_, send one to the chat with yourself, and also
download the profile photo of the channel. `asyncio` will run all these
three tasks at the same time. You can run all the tasks you want this way.

A different way would be:

.. code-block:: python

    loop.create_task(client.get_messages('telegram', 10))
    loop.create_task(client.send_message('me', 'Using asyncio!'))
    loop.create_task(client.download_profile_photo('telegram'))

They will run in the background as long as the loop is running too.

You can also `start an asyncio server
<https://docs.python.org/3/library/asyncio-stream.html#asyncio.start_server>`_
in the main script, and from another script, `connect to it
<https://docs.python.org/3/library/asyncio-stream.html#asyncio.open_connection>`_
to achieve `Inter-Process Communication
<https://en.wikipedia.org/wiki/Inter-process_communication>`_.
You can get as creative as you want. You can program anything you want.
When you use a library, you're not limited to use only its methods. You can
combine all the libraries you want. People seem to forget this simple fact!


Why does client.start() work outside async?
===========================================

Because it's so common that it's really convenient to offer said
functionality by default. This means you can set up all your event
handlers and start the client without worrying about loops at all.

Using the client in a ``with`` block, `start
<telethon.client.auth.AuthMethods.start>`, `run_until_disconnected
<telethon.client.updates.UpdateMethods.run_until_disconnected>`, and
`disconnect <telethon.client.telegrambaseclient.TelegramBaseClient.disconnect>`
all support this.

Where can I read more?
======================

`Check out my blog post
<https://lonami.dev/blog/asyncio/>`_ about `asyncio`, which
has some more examples and pictures to help you understand what happens
when the loop runs.
