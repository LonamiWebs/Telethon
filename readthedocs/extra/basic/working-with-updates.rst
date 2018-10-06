.. _working-with-updates:

====================
Working with Updates
====================

.. important::

    Coming from Telethon before it reached its version 1.0?
    Make sure to read :ref:`compatibility-and-convenience`!
    Otherwise, you can ignore this note and just follow along.

The library comes with the `telethon.events` module. *Events* are an abstraction
over what Telegram calls `updates`__, and are meant to ease simple and common
usage when dealing with them, since there are many updates. If you're looking
for the method reference, check :ref:`telethon-events-package`, otherwise,
let's dive in!


.. important::

    The library logs by default no output, and any exception that occurs
    inside your handlers will be "hidden" from you to prevent the thread
    from terminating (so it can still deliver events). You should enable
    logging when working with events, at least the error level, to see if
    this is happening so you can debug the error.

    **When using updates, please enable logging:**

    .. code-block:: python

        import logging
        logging.basicConfig(level=logging.ERROR)


.. contents::


Getting Started
***************

.. code-block:: python

    from telethon import TelegramClient, events

    client = TelegramClient('name', api_id, api_hash)

    @client.on(events.NewMessage)
    async def my_event_handler(event):
        if 'hello' in event.raw_text:
            await event.reply('hi!')

    client.start()
    client.run_until_disconnected()


Not much, but there might be some things unclear. What does this code do?

.. code-block:: python

    from telethon import TelegramClient, events

    client = TelegramClient('name', api_id, api_hash)


This is normal creation (of course, pass session name, API ID and hash).
Nothing we don't know already.

.. code-block:: python

    @client.on(events.NewMessage)


This Python decorator will attach itself to the ``my_event_handler``
definition, and basically means that *on* a `NewMessage
<telethon.events.newmessage.NewMessage>` *event*,
the callback function you're about to define will be called:

.. code-block:: python

    async def my_event_handler(event):
        if 'hello' in event.raw_text:
            await event.reply('hi!')


If a `NewMessage
<telethon.events.newmessage.NewMessage>` event occurs,
and ``'hello'`` is in the text of the message, we `.reply()
<telethon.tl.custom.message.Message.reply>` to the event
with a ``'hi!'`` message.

Do you notice anything different? Yes! Event handlers **must** be ``async``
for them to work, and **every method using the network** needs to have an
``await``, otherwise, Python's ``asyncio`` will tell you that you forgot
to do so, so you can easily add it.

.. code-block:: python

    client.start()
    client.run_until_disconnected()


Finally, this tells the client that we're done with our code. We run the
``asyncio`` loop until the client starts (this is done behind the scenes,
since the method is so common), and then we run it again until we are
disconnected. Of course, you can do other things instead of running
until disconnected. For this refer to :ref:`update-modes`.


More on events
**************

The `NewMessage <telethon.events.newmessage.NewMessage>` event has much
more than what was shown. You can access the `.sender
<telethon.tl.custom.message.Message.sender>` of the message
through that member, or even see if the message had `.media
<telethon.tl.custom.message.Message.media>`, a `.photo
<telethon.tl.custom.message.Message.photo>` or a `.document
<telethon.tl.custom.message.Message.document>` (which you
could download with for example `client.download_media(event.photo)
<telethon.client.downloads.DownloadMethods.download_media>`.

If you don't want to `.reply()
<telethon.tl.custom.message.Message.reply>` as a reply,
you can use the `.respond() <telethon.tl.custom.message.Message.respond>`
method instead. Of course, there are more events such as `ChatAction
<telethon.events.chataction.ChatAction>` or `UserUpdate
<telethon.events.userupdate.UserUpdate>`, and they're all
used in the same way. Simply add the `@client.on(events.XYZ)
<telethon.client.updates.UpdateMethods.on>` decorator on the top
of your handler and you're done! The event that will be passed always
is of type ``XYZ.Event`` (for instance, `NewMessage.Event
<telethon.events.newmessage.NewMessage.Event>`), except for the `Raw
<telethon.events.raw.Raw>` event which just passes the :tl:`Update` object.

Note that `.reply()
<telethon.tl.custom.message.Message.reply>` and `.respond()
<telethon.tl.custom.message.Message.respond>` are just wrappers around the
`client.send_message() <telethon.client.messages.MessageMethods.send_message>`
method which supports the ``file=`` parameter.
This means you can reply with a photo if you do `event.reply(file=photo)
<telethon.tl.custom.message.Message.reply>`.

You can put the same event on many handlers, and even different events on
the same handler. You can also have a handler work on only specific chats,
for example:


.. code-block:: python

    import ast
    import random


    # Either a single item or a list of them will work for the chats.
    # You can also use the IDs, Peers, or even User/Chat/Channel objects.
    @client.on(events.NewMessage(chats=('TelethonChat', 'TelethonOffTopic')))
    async def normal_handler(event):
        if 'roll' in event.raw_text:
            await event.reply(str(random.randint(1, 6)))


    # Similarly, you can use incoming=True for messages that you receive
    @client.on(events.NewMessage(chats='TelethonOffTopic', outgoing=True,
                                 pattern='eval (.+)'))
    async def admin_handler(event):
        expression = event.pattern_match.group(1)
        await event.reply(str(ast.literal_eval(expression)))


You can pass one or more chats to the ``chats`` parameter (as a list or tuple),
and only events from there will be processed. You can also specify whether you
want to handle incoming or outgoing messages (those you receive or those you
send). In this example, people can say ``'roll'`` and you will reply with a
random number, while if you say ``'eval 4+4'``, you will reply with the
solution. Try it!


Properties vs. Methods
**********************

The event shown above acts just like a `custom.Message
<telethon.tl.custom.message.Message>`, which means you
can access all the properties it has, like ``.sender``.

**However** events are different to other methods in the client, like
`client.get_messages <telethon.client.messages.MessageMethods.get_messages>`.
Events *may not* send information about the sender or chat, which means it
can be ``None``, but all the methods defined in the client always have this
information so it doesn't need to be re-fetched. For this reason, you have
``get_`` methods, which will make a network call if necessary.

In short, you should do this:

.. code-block:: python

    @client.on(events.NewMessage)
    async def handler(event):
        # event.input_chat may be None, use event.get_input_chat()
        chat = await event.get_input_chat()
        sender = await event.get_sender()
        buttons = await event.get_buttons()

    async def main():
        async for message in client.iter_messages('me', 10):
            # Methods from the client always have these properties ready
            chat = message.input_chat
            sender = message.sender
            buttons = message.buttons

Notice, properties (`message.sender
<telethon.tl.custom.message.Message.sender>`) don't need an ``await``, but
methods (`message.get_sender
<telethon.tl.custom.message.Message.get_sender>`) **do** need an ``await``,
and you should use methods in events for these properties that may need network.


Events Without the client
*************************

The code of your application starts getting big, so you decide to
separate the handlers into different files. But how can you access
the client from these files? You don't need to! Just `events.register
<telethon.events.register>` them:

.. code-block:: python

    # handlers/welcome.py
    from telethon import events

    @events.register(events.NewMessage('(?i)hello'))
    async def handler(event):
        client = event.client
        await event.respond('Hey!')
        await client.send_message('me', 'I said hello to someone')


Registering events is a way of saying "this method is an event handler".
You can use `telethon.events.is_handler` to check if any method is a handler.
You can think of them as a different approach to Flask's blueprints.

It's important to note that this does **not** add the handler to any client!
You never specified the client on which the handler should be used. You only
declared that it is a handler, and its type.

To actually use the handler, you need to `client.add_event_handler
<telethon.client.updates.UpdateMethods.add_event_handler>` to the
client (or clients) where they should be added to:

.. code-block:: python

    # main.py
    from telethon import TelegramClient
    import handlers.welcome

    with TelegramClient(...) as client:
        client.add_event_handler(handlers.welcome.handler)
        client.run_until_disconnected()


This also means that you can register an event handler once and
then add it to many clients without re-declaring the event.


Events Without Decorators
*************************

If for any reason you don't want to use `telethon.events.register`,
you can explicitly pass the event handler to use to the mentioned
`client.add_event_handler
<telethon.client.updates.UpdateMethods.add_event_handler>`:

.. code-block:: python

    from telethon import TelegramClient, events

    async def handler(event):
        ...

    with TelegramClient(...) as client:
        client.add_event_handler(handler, events.NewMessage)
        client.run_until_disconnected()


Similarly, you also have `client.remove_event_handler
<telethon.client.updates.UpdateMethods.remove_event_handler>`
and `client.list_event_handlers
<telethon.client.updates.UpdateMethods.list_event_handlers>`.

The ``event`` argument is optional in all three methods and defaults to
`events.Raw <telethon.events.raw.Raw>` for adding, and ``None`` when
removing (so all callbacks would be removed).

.. note::

    The ``event`` type is ignored in `client.add_event_handler
    <telethon.client.updates.UpdateMethods.add_event_handler>`
    if you have used `telethon.events.register` on the ``callback``
    before, since that's the point of using such method at all.


Stopping Propagation of Updates
*******************************

There might be cases when an event handler is supposed to be used solitary and
it makes no sense to process any other handlers in the chain. For this case,
it is possible to raise a `telethon.events.StopPropagation` exception which
will cause the propagation of the update through your handlers to stop:

.. code-block:: python

    from telethon.events import StopPropagation

    @client.on(events.NewMessage)
    async def _(event):
        # ... some conditions
        await event.delete()

        # Other handlers won't have an event to work with
        raise StopPropagation

    @client.on(events.NewMessage)
    async def _(event):
        # Will never be reached, because it is the second handler
        # in the chain.
        pass


Remember to check :ref:`telethon-events-package` if you're looking for
the methods reference.


__ https://lonamiwebs.github.io/Telethon/types/update.html
