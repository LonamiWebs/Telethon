.. _asyncio-crash-course:

===========================
A Crash Course into asyncio
===========================


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


Inside ``async def main():``, you can use the ``await`` keyword. Most
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
`await client.disconnected <telethon.client.telegrambaseclient.TelegramBaseClient.disconnected>`
which is a property that you can wait on until you call
`await client.disconnect() <telethon.client.telegrambaseclient.TelegramBaseClient.disconnect>`:


.. code-block:: python

    client = TelegramClient(...)

    @client.on(events.NewMessage)
    async def handler(event):
        print(event)

    async def main():
        await client.start()
        await client.disconnected

    if __name__ == '__main__':
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())

This is the same as using the ``run_until_disconnected()`` method:

.. code-block:: python

    client = TelegramClient(...)

    @client.on(events.NewMessage)
    async def handler(event):
        print(event)

    if __name__ == '__main__':
        loop = asyncio.get_event_loop()
        loop.run_until_complete(client.start())
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

The documentation will use all these three styles so you can get used
to them. Which one to use is up to you, but generally you should work
inside an ``async def main()`` and just run the loop there.


More resources to learn asyncio
*******************************

If you would like to learn a bit more about why ``asyncio`` is something
you should learn, `check out my blog post
<https://lonamiwebs.github.io/blog/asyncio/>`_ that goes into more detail.
