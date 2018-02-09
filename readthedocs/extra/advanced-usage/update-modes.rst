.. _update-modes:

============
Update Modes
============


The library can run in four distinguishable modes:

- With no extra threads at all.
- With an extra thread that receives everything as soon as possible (default).
- With several worker threads that run your update handlers.
- A mix of the above.

Since this section is about updates, we'll describe the simplest way to
work with them.


Using multiple workers
**********************

When you create your client, simply pass a number to the
``update_workers`` parameter:

    ``client = TelegramClient('session', api_id, api_hash, update_workers=2)``

You can set any amount of workers you want. The more you put, the more
update handlers that can be called "at the same time". One or two should
suffice most of the time, since setting more will not make things run
faster most of the times (actually, it could slow things down).

The next thing you want to do is to add a method that will be called when
an `Update`__ arrives:

    .. code-block:: python

        def callback(update):
            print('I received', update)

        client.add_update_handler(callback)
        # do more work here, or simply sleep!

That's it! This is the old way to listen for raw updates, with no further
processing. If this feels annoying for you, remember that you can always
use :ref:`working-with-updates` but maybe use this for some other cases.

Now let's do something more interesting. Every time an user talks to use,
let's reply to them with the same text reversed:

    .. code-block:: python

        from telethon.tl.types import UpdateShortMessage, PeerUser

        def replier(update):
            if isinstance(update, UpdateShortMessage) and not update.out:
                client.send_message(PeerUser(update.user_id), update.message[::-1])


        client.add_update_handler(replier)
        input('Press enter to stop this!')
        client.disconnect()

We only ask you one thing: don't keep this running for too long, or your
contacts will go mad.


Spawning no worker at all
*************************

All the workers do is loop forever and poll updates from a queue that is
filled from the ``ReadThread``, responsible for reading every item off
the network. If you only need a worker and the ``MainThread`` would be
doing no other job, this is the preferred way. You can easily do the same
as the workers like so:

    .. code-block:: python

        while True:
            try:
                update = client.updates.poll()
                if not update:
                    continue

                print('I received', update)
            except KeyboardInterrupt:
                break

        client.disconnect()

Note that ``poll`` accepts a ``timeout=`` parameter, and it will return
``None`` if other thread got the update before you could or if the timeout
expired, so it's important to check ``if not update``.

This can coexist with the rest of ``N`` workers, or you can set it to ``0``
additional workers:

    ``client = TelegramClient('session', api_id, api_hash, update_workers=0)``

You **must** set it to ``0`` (or other number), as it defaults to ``None``
and there is a different. ``None`` workers means updates won't be processed
*at all*, so you must set it to some value (``0`` or greater) if you want
``client.updates.poll()`` to work.


Using the main thread instead the ``ReadThread``
************************************************

If you have no work to do on the ``MainThread`` and you were planning to have
a ``while True: sleep(1)``, don't do that. Instead, don't spawn the secondary
``ReadThread`` at all like so:

    .. code-block:: python

        client = TelegramClient(
            ...
            spawn_read_thread=False
        )

And then ``.idle()`` from the ``MainThread``:

    ``client.idle()``

You can stop it with :kbd:`Control+C`, and you can configure the signals
to be used in a similar fashion to `Python Telegram Bot`__.

As a complete example:

    .. code-block:: python

        def callback(update):
            print('I received', update)

        client = TelegramClient('session', api_id, api_hash,
                                update_workers=1, spawn_read_thread=False)

        client.connect()
        client.add_update_handler(callback)
        client.idle()  # ends with Ctrl+C


This is the preferred way to use if you're simply going to listen for updates.

__ https://lonamiwebs.github.io/Telethon/types/update.html
__ https://github.com/python-telegram-bot/python-telegram-bot/blob/4b3315db6feebafb94edcaa803df52bb49999ced/telegram/ext/updater.py#L460
