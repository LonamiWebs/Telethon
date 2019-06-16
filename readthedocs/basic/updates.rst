=======
Updates
=======

Updates are an important topic in a messaging platform like Telegram.
After all, you want to be notified when a new message arrives, when
a member joins, when someone starts typing, etc.
For that, you can use **events**.

.. important::

    It is strongly advised to enable logging when working with events,
    since exceptions in event handlers are hidden by default. Please
    add the following snippet to the very top of your file:

    .. code-block:: python

        import logging
        logging.basicConfig(format='[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s',
                            level=logging.WARNING)


Getting Started
===============

Let's start things with an example to automate replies:

.. code-block:: python

    from telethon import TelegramClient, events

    client = TelegramClient('anon', api_id, api_hash)

    @client.on(events.NewMessage)
    async def my_event_handler(event):
        if 'hello' in event.raw_text:
            await event.reply('hi!')

    client.start()
    client.run_until_disconnected()


This code isn't much, but there might be some things unclear.
Let's break it down:

.. code-block:: python

    from telethon import TelegramClient, events

    client = TelegramClient('anon', api_id, api_hash)


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
and ``'hello'`` is in the text of the message, we `reply()
<telethon.tl.custom.message.Message.reply>` to the event
with a ``'hi!'`` message.

.. note::

    Event handlers **must** be ``async def``. After all,
    Telethon is an asynchronous library based on `asyncio`,
    which is a safer and often faster approach to threads.

    You **must** ``await`` all method calls that use
    network requests, which is most of them.


More Examples
=============

Replying to messages with hello is fun, but, can we do more?

.. code-block:: python

    @client.on(events.NewMessage(outgoing=True, pattern=r'\.save'))
    async def handler(event):
        if event.is_reply:
            replied = await event.get_reply_message()
            sender = replied.sender
            await client.download_profile_photo(sender)
            await event.respond('Saved your photo {}'.format(sender.username))

We could also get replies. This event filters outgoing messages
(only those that we send will trigger the method), then we filter
by the regex ``r'\.save'``, which will match messages starting
with ``".save"``.

Inside the method, we check whether the event is replying to another message
or not. If it is, we get the reply message and the sender of that message,
and download their profile photo.

Let's delete messages which contain "heck". We don't allow swearing here.

.. code-block:: python

    @client.on(events.NewMessage(pattern=r'(?i).*heck'))
    async def handler(event):
        await event.delete()


With the ``r'(?i).*heck'`` regex, we match case-insensitive
"heck" anywhere in the message. Regex is very powerful and you
can learn more at https://regexone.com/.

So far, we have only seen the `NewMessage
<telethon.events.newmessage.NewMessage>`, but there are many more
which will be covered later. This is only a small introduction to updates.

Entities
========

When you need the user or chat where an event occurred, you **must** use
the following methods:

.. code-block:: python

    async def handler(event):
        # Good
        chat = await event.get_chat()
        sender = await event.get_sender()
        chat_id = event.chat_id
        sender_id = event.sender_id

        # BAD. Don't do this
        chat = event.chat
        sender = event.sender
        chat_id = event.chat.id
        sender_id = event.sender.id

Events are like messages, but don't have all the information a message has!
When you manually get a message, it will have all the information it needs.
When you receive an update about a message, it **won't** have all the
information, so you have to **use the methods**, not the properties.

Make sure you understand the code seen here before continuing!
As a rule of thumb, remember that new message events behave just
like message objects, so you can do with them everything you can
do with a message object.
