.. _update-modes:

============
Update Modes
============

Using ``asyncio`` simplifies the way you can work with updates. The library
will always ensure the future of a loop that will poll updates for you, so
you can do other things in the mean time.

Once you have your client ready, the next thing you want to do is to add a
method that will be called when an `Update`__ arrives:

    .. code-block:: python

        import asyncio
        loop = asyncio.get_event_loop()

        async def callback(update):
            print('I received', update)

        loop.run_until_complete(client.add_event_handler(callback))
        loop.run_forever()  # this blocks forever, don't let the script end!

That's it! This is the old way to listen for raw updates, with no further
processing. If this feels annoying for you, remember that you can always
use :ref:`working-with-updates` but maybe use this for some other cases.

Now let's do something more interesting. Every time an user talks to us,
let's reply to them with the same text reversed:

    .. code-block:: python

        from telethon.tl.types import UpdateShortMessage, PeerUser

        async def replier(update):
            if isinstance(update, UpdateShortMessage) and not update.out:
                await client.send_message(PeerUser(update.user_id), update.message[::-1])


        loop.run_until_complete(client.add_event_handler(replier))
        loop.run_forever()

We only ask you one thing: don't keep this running for too long, or your
contacts will go mad.


This is the preferred way to use if you're simply going to listen for updates.

__ https://lonamiwebs.github.io/Telethon/types/update.html
