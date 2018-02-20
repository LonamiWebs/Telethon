.. _working-with-updates:

====================
Working with Updates
====================


The library comes with the :mod:`events` module. *Events* are an abstraction
over what Telegram calls `updates`__, and are meant to ease simple and common
usage when dealing with them, since there are many updates. Let's dive in!


.. contents::


Getting Started
***************

    .. code-block:: python

        from telethon import TelegramClient, events

        client = TelegramClient(..., update_workers=1, spawn_read_thread=False)
        client.start()

        @client.on(events.NewMessage)
        def my_event_handler(event):
            if 'hello' in event.raw_text:
                event.reply('hi!')

        client.idle()


Not much, but there might be some things unclear. What does this code do?

    .. code-block:: python

        from telethon import TelegramClient, events

        client = TelegramClient(..., update_workers=1, spawn_read_thread=False)
        client.start()


This is normal initialization (of course, pass session name, API ID and hash).
Nothing we don't know already.

    .. code-block:: python

        @client.on(events.NewMessage)


This Python decorator will attach itself to the ``my_event_handler``
definition, and basically means that *on* a ``NewMessage`` *event*,
the callback function you're about to define will be called:

    .. code-block:: python

        def my_event_handler(event):
            if 'hello' in event.raw_text:
                event.reply('hi!')


If a ``NewMessage`` event occurs, and ``'hello'`` is in the text of the
message, we ``reply`` to the event with a ``'hi!'`` message.

    .. code-block:: python

        client.idle()


Finally, this tells the client that we're done with our code, and want
to listen for all these events to occur. Of course, you might want to
do other things instead idling. For this refer to :ref:`update-modes`.


More on events
**************

The ``NewMessage`` event has much more than what was shown. You can access
the ``.sender`` of the message through that member, or even see if the message
had ``.media``, a ``.photo`` or a ``.document`` (which you could download with
for example ``client.download_media(event.photo)``.

If you don't want to ``.reply`` as a reply, you can use the ``.respond()``
method instead. Of course, there are more events such as ``ChatAction`` or
``UserUpdate``, and they're all used in the same way. Simply add the
``@client.on(events.XYZ)`` decorator on the top of your handler and you're
done! The event that will be passed always is of type ``XYZ.Event`` (for
instance, ``NewMessage.Event``), except for the ``Raw`` event which just
passes the ``Update`` object.

You can put the same event on many handlers, and even different events on
the same handler. You can also have a handler work on only specific chats,
for example:


    .. code-block:: python

        import ast
        import random


        @client.on(events.NewMessage(chats='TelethonOffTopic', incoming=True))
        def normal_handler(event):
            if 'roll' in event.raw_text:
                event.reply(str(random.randint(1, 6)))


        @client.on(events.NewMessage(chats='TelethonOffTopic', outgoing=True))
        def admin_handler(event):
            if event.raw_text.startswith('eval'):
                expression = event.raw_text.replace('eval', '').strip()
                event.reply(str(ast.literal_eval(expression)))


You can pass one or more chats to the ``chats`` parameter (as a list or tuple),
and only events from there will be processed. You can also specify whether you
want to handle incoming or outgoing messages (those you receive or those you
send). In this example, people can say ``'roll'`` and you will reply with a
random number, while if you say ``'eval 4+4'``, you will reply with the
solution. Try it!


Stopping propagation of Updates
*******************************

There might be cases when an event handler is supposed to be used solitary and
it makes no sense to process any other handlers in the chain. For this case,
it is possible to raise a ``StopPropagation`` exception which will cause the
propagation of the update through your handlers to stop:

    .. code-block:: python

        @client.on(events.NewMessage)
        def _(event):
            # ... some conditions
            event.delete()

            # Other handlers won't have an event to work with
            raise client.StopPropagation

        @client.on(events.NewMessage)
        def _(event):
            pass  # Will never be reached, because
                  # it is the second handler in the chain.


Events module
*************

.. automodule:: telethon.events
    :members:
        :undoc-members:
        :show-inheritance:



__ https://lonamiwebs.github.io/Telethon/types/update.html
