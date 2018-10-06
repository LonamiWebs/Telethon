.. _update-modes:

============
Update Modes
============

With ``asyncio``, the library has several tasks running in the background.
One task is used for sending requests, another task is used to receive them,
and a third one is used to handle updates.

To handle updates, you must keep your script running. You can do this in
several ways. For instance, if you are *not* running ``asyncio``'s event
loop, you should use `client.run_until_disconnected
<telethon.client.updates.UpdateMethods.run_until_disconnected>`:

.. code-block:: python

    import asyncio
    from telethon import TelegramClient

    client = TelegramClient(...)
    ...
    client.run_until_disconnected()


Behind the scenes, this method is ``await``'ing on the `client.disconnected
<telethon.client.telegrambaseclient.TelegramBaseClient.disconnected>` property,
so the code above and the following are equivalent:

.. code-block:: python

    import asyncio
    from telethon import TelegramClient

    client = TelegramClient(...)

    async def main():
        await client.disconnected

    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())


You could also run `client.disconnected
<telethon.client.telegrambaseclient.TelegramBaseClient.disconnected>`
until it completed.

But if you don't want to ``await``, then you should know what you want
to be doing instead! What matters is that you shouldn't let your script
die. If you don't care about updates, you don't need any of this.

Notice that unlike `client.disconnected
<telethon.client.telegrambaseclient.TelegramBaseClient.disconnected>`,
`client.run_until_disconnected
<telethon.client.updates.UpdateMethods.run_until_disconnected>` will
handle ``KeyboardInterrupt`` with you. This method is special and can
also be ran while the loop is running, so you can do this:

.. code-block:: python

    async def main():
        await client.run_until_disconnected()

    loop.run_until_complete(main())


If you need to process updates sequentially (i.e. not in parallel),
you should set ``sequential_updates=True`` when creating the client:

.. code-block:: python

    with TelegramClient(..., sequential_updates=True) as client:
        ...
