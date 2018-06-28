.. _asyncio-magic:

==================
Magic with asyncio
==================

.. important::

    TL; DR; If you've upgraded to Telethon 1.0 from a previous version
    **and you're not using events or updates**, add this line:

    .. code-block:: python

        import telethon.sync

    At the beginning of your main script and you will be good. If you **do**
    use updates or events, keep reading, or ``pip install telethon-sync``, a
    branch that mimics the ``asyncio`` code with threads and should work
    under Python 3.4.

    You might also want to check the :ref:`changelog`.


The sync module
***************

It's time to tell you the truth. The library has been doing magic behind
the scenes. We're sorry to tell you this, but at least it wasn't dark magic!

You may have noticed one of these lines across the documentation:

.. code-block:: python

    from telethon import sync
    # or
    import telethon.sync

Either of these lines will import the *magic* ``sync`` module. When you
import this module, you can suddenly use all the methods defined in the
:ref:`TelegramClient <telethon-client>` like so:

.. code-block:: python

    client.send_message('me', 'Hello!')

    for dialog in client.iter_dialogs():
        print(dialog.title)


What happened behind the scenes is that all those methods, called *coroutines*,
were rewritten to be normal methods that will block (with some exceptions).
This means you can use the library without worrying about ``asyncio`` and
event loops.

However, this only works until you run the event loop yourself explicitly:

.. code-block:: python

    import asyncio

    async def coro():
        client.send_message('me', 'Hello!')  # <- no longer works!

    loop = asyncio.get_event_loop()
    loop.run_until_complete(coro())


What things will work and when?
*******************************

You can use all the methods in the :ref:`TelegramClient <telethon-client>`
in a synchronous, blocking way without trouble, as long as you're not running
the loop as we saw above (the ``loop.run_until_complete(...)`` line runs "the
loop"). If you're running the loop, then *you* are the one responsible to
``await`` everything. So to fix the code above:

.. code-block:: python

    import asyncio

    async def coro():
        await client.send_message('me', 'Hello!')
        # ^ notice this new await

    loop = asyncio.get_event_loop()
    loop.run_until_complete(coro())

The library can only run the loop until the method completes if the loop
isn't already running, which is why the magic can't work if you run the
loop yourself.

**When you work with updates or events**, the loop needs to be
running one way or another (using `client.run_until_disconnected()
<telethon.client.updates.UpdateMethods.run_until_disconnected>` runs the loop),
so your event handlers must be ``async def``.

.. important::

    Turning your event handlers into ``async def`` is the biggest change
    between Telethon pre-1.0 and 1.0, but updating will likely cause a
    noticeable speed-up in your programs. Keep reading!


So in short, you can use **all** methods in the client with ``await`` or
without it if the loop isn't running:

.. code-block:: python

    client.send_message('me', 'Hello!')  # works

    async def main():
        await client.send_message('me', 'Hello!')  # also works

    loop.run_until_complete(main())


When you work with updates, you should stick using the ``async def main``
way, since your event handlers will be ``async def`` too.

.. note::

    There are two exceptions. Both `client.run_until_disconnected()
    <telethon.client.updates.UpdateMethods.run_until_disconnected>` and
    `client.start() <telethon.client.auth.AuthMethods.start>` work in
    and outside of ``async def`` for convenience without importing the
    magic module. The rest of methods remain ``async`` unless you import it.

You can skip the rest if you already know how ``asyncio`` works and you
already understand what the magic does and how it works. Just remember
to ``await`` all your methods if you're inside an ``async def`` or are
using updates and you will be good.


Why asyncio?
************

Python's `asyncio <https://docs.python.org/3/library/asyncio.html>`_ is the
standard way to run asynchronous code from within Python. Since Python 3.5,
using ``async def`` and ``await`` became possible, and Python 3.6 further
improves what you can do with asynchronous code, although it's not the only
way (other projects like `Trio <https://github.com/python-trio>`_ also exist).

Telegram is a service where all API calls are executed in an asynchronous
way. You send your request, and eventually, Telegram will process it and
respond to it. It feels natural to make a library that also behaves this
way: you send a request, and you can ``await`` for its result.

Now that we know that Telegram's API follows an asynchronous model, you
should understand the benefits of developing a library that does the same,
it greatly simplifies the internal code and eases working with the API.

Using ``asyncio`` keeps a cleaner library that will be easier to understand,
develop, and that will be faster than using threads, which are harder to get
right and can cause issues. It also enables to use the powerful ``asyncio``
system such as futures, timeouts, cancellation, etc. in a natural way.

If you're still not convinced or you're just not ready for using ``asyncio``,
the library offers a synchronous interface without the need for all the
``async`` and ``await`` you would otherwise see. `Follow this link
<https://github.com/LonamiWebs/Telethon/tree/sync>`_ to find out more.


How do I get started?
*********************

To get started with ``asyncio``, all you need is to setup your main
``async def`` like so:

.. code-block:: python

    import asyncio

    async def main():
        pass  # Your code goes here

    if __name__ == '__main__':
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())

You don't need to ``import telethon.sync`` if you're going to work this
way. This is the best way to work in real programs since the loop won't
be starting and ending all the time, but is a bit more annoying to setup.

Inside ``async def main()``, you can use the ``await`` keyword. Most
methods in the :ref:`TelegramClient <telethon-client>` are ``async def``.
You must ``await`` all ``async def``, also known as a *coroutines*:

.. code-block:: python

    async def main():
        client = TelegramClient(...)

        # client.start() is a coroutine (async def), it needs an await
        await client.start()

        # Sending a message also interacts with the API, and needs an await
        await client.send_message('me', 'Hello myself!')


If you don't know anything else about ``asyncio``, this will be enough
to get you started. Once you're ready to learn more about it, you will
be able to use that power and everything you've learnt with Telethon.
Just remember that if you use ``await``, you need to be inside of an
``async def``.

Another way to use ``async def`` is to use ``loop.run_until_complete(f())``,
but the loop must not be running before.

If you want to handle updates (and don't let the script die), you must
`await client.run_until_disconnected()
<telethon.client.updates.UpdateMethods.run_until_disconnected>`
which is a property that you can wait on until you call
`await client.disconnect()
<telethon.client.telegrambaseclient.TelegramBaseClient.disconnect>`:


.. code-block:: python

    client = TelegramClient(...)

    @client.on(events.NewMessage)
    async def handler(event):
        print(event)

    async def main():
        await client.start()
        await client.run_until_disconnected()

    if __name__ == '__main__':
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())

`client.run_until_disconnected()
<telethon.client.updates.UpdateMethods.run_until_disconnected>` and
`client.start()
<telethon.client.auth.AuthMethods.start>` are special-cased and work
inside or outside ``async def`` for convenience, even without importing
the ``sync`` module, so you can also do this:

.. code-block:: python

    client = TelegramClient(...)

    @client.on(events.NewMessage)
    async def handler(event):
        print(event)

    if __name__ == '__main__':
        client.start()
        client.run_until_disconnected()


Which methods should I use and when?
************************************

Something to note is that you must always get an event loop if you
want to be able to make any API calls. This is done as follows:

.. code-block:: python

    import asyncio
    loop = asyncio.get_event_loop()

The loop must be running, or things will never get sent.
Normally, you use ``run_until_complete``:

.. code-block:: python

    async def coroutine():
        await asyncio.sleep(1)

    loop.run_until_complete(coroutine())

Note that ``asyncio.sleep`` is in itself a coroutine, so this will
work too:

.. code-block:: python

    loop.run_until_complete(asyncio.sleep(1))

Generally, you make an ``async def main()`` if you need to ``await``
a lot of things, instead of typing ``run_until_complete`` all the time:

.. code-block:: python

    async def main():
        message = await client.send_message('me', 'Hi')
        await asyncio.sleep(1)
        await message.delete()

    loop.run_until_complete(main())

    # vs

    message = loop.run_until_complete(client.send_message('me', 'Hi'))
    loop.run_until_complete(asyncio.sleep(1))
    loop.run_until_complete(message.delete())

You can see that the first version has more lines, but you had to type
a lot less. You can also rename the run method to something shorter:

.. code-block:: python

    # Note no parenthesis (), we're not running it, just copying the method
    rc = loop.run_until_complete
    message = rc(client.send_message('me', 'Hi'))
    rc(asyncio.sleep(1))
    rc(message.delete())

The documentation generally runs the loop until complete behind the
scenes if you've imported the magic ``sync`` module, but if you haven't,
you need to run the loop yourself. We recommend that you use the
``async def main()`` method to do all your work with ``await``.
It's the easiest and most performant thing to do.


More resources to learn asyncio
*******************************

If you would like to learn a bit more about why ``asyncio`` is something
you should learn, `check out my blog post
<https://lonamiwebs.github.io/blog/asyncio/>`_ that goes into more detail.
