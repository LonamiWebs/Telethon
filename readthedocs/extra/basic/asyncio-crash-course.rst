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

Having understood that Telegram's API follows an asynchronous model and
developing a library that does the same greatly simplifies the internal
code and eases working with the API.

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
You must ``await`` all ``async def``, also known as a coroutine:

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
`await client.disconnected <telethon.client.telegrambaseclient.disconnected>`
which is a property that you can wait on until you call
`await client.disconnect() <telethon.client.telegrambaseclient.disconnect>`:


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


More resources to learn asyncio
*******************************

If you would like to learn a bit more about why ``asyncio`` is something
you should learn, `check out my blog post
<https://lonamiwebs.github.io/blog/asyncio/>`_ that goes into more detail.
