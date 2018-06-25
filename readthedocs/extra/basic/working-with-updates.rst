.. _working-with-updates:

====================
Working with Updates
====================

.. important::

    Make sure you have read at least the first part of :ref:`asyncio-magic`
    before working with updates. **This is a big change from Telethon pre-1.0
    and 1.0, and your old handlers won't work with this version**.

    To port your code to the new version, you should just prefix all your
    event handlers with ``async`` and ``await`` everything that makes an
    API call, such as replying, deleting messages, etc.


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


Properties vs. methods
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


Events without decorators
*************************

If for any reason you can't use the `@client.on
<telethon.client.updates.UpdateMethods.on>` syntax, don't worry.
You can call `client.add_event_handler(callback, event)
<telethon.client.updates.UpdateMethods.add_event_handler>` to achieve
the same effect.

Similarly, you also have `client.remove_event_handler
<telethon.client.updates.UpdateMethods.remove_event_handler>`
and `client.list_event_handlers
<telethon.client.updates.UpdateMethods.list_event_handlers>`.

The ``event`` type is optional in all methods and defaults to
`events.Raw <telethon.events.raw.Raw>` for adding, and ``None`` when
removing (so all callbacks would be removed).


Stopping propagation of Updates
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
