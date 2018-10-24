.. _telegram-client-example:


========================
Examples with the Client
========================

This section explores the methods defined in the :ref:`telegram-client`
with some practical examples. The section assumes that you have imported
the ``telethon.sync`` package and that you have a client ready to use.


.. note::

    There are some very common errors (such as forgetting to add
    ``import telethon.sync``) for newcomers to ``asyncio``:

    .. code-block:: python

        # AttributeError: 'coroutine' object has no attribute 'first_name'
        print(client.get_me().first_name)

        # TypeError: 'AsyncGenerator' object is not iterable
        for message in client.iter_messages('me'):
            ...

        # RuntimeError: This event loop is already running
        with client.conversation('me') as conv:
            ...

    That error means you're probably inside an ``async def`` so you
    need to use:

    .. code-block:: python

        print((await client.get_me()).first_name)
        async for message in client.iter_messages('me'):
            ...

        async with client.conversation('me') as conv:
            ...

    You can of course call other ``def`` functions from your ``async def``
    event handlers, but if they need making API calls, make your own
    functions ``async def`` so you can ``await`` things:

    .. code-block:: python

        async def helper(client):
            await client.send_message('me', 'Hi')

    If you're not inside an ``async def`` you can enter one like so:

    .. code-block:: python

        import asyncio
        loop = asyncio.get_event_loop()
        loop.run_until_complete(my_async_def())


.. contents::


Authorization
*************

Starting the client is as easy as calling `client.start()
<telethon.client.auth.AuthMethods.start>`:

.. code-block:: python

    client.start()
    ...  # code using the client
    client.disconnect()

And you can even use a ``with`` block:

.. code-block:: python

    with client:
        ... # code using the client


.. note::

    Remember we assume you have ``import telethon.sync``. You can of course
    use the library without importing it. The code would be rewritten as:

    .. code-block:: python

        import asyncio
        loop = asyncio.get_event_loop()

        async def main():
            await client.start()
            ...
            await client.disconnect()

            # or
            async with client:
                ...

        loop.run_until_complete(main())

    All methods that need access to the network (e.g. to make an API call)
    **must** be awaited (or their equivalent such as ``async for`` and
    ``async with``). You can do this yourself or you can let the library
    do it for you by using ``import telethon.sync``. With event handlers,
    you must do this yourself.

The cleanest way to delete your ``*.session`` file is `client.log_out
<telethon.client.auth.AuthMethods.log_out>`. Note that you will obviously
need to login again if you use this:

.. code-block:: python

    # Logs out and deletes the session file; you will need to sign in again
    client.log_out()

    # You often simply want to disconnect. You will not need to sign in again
    client.disconnect()


Group Chats
***********

You can easily iterate over all the :tl:`User` in a chat and
do anything you want with them by using `client.iter_participants
<telethon.client.chats.ChatMethods.iter_participants>`:

.. code-block:: python

    for user in client.iter_participants(chat):
        ...  # do something with the user

You can also search by their name:

.. code-block:: python

    for user in client.iter_participants(chat, search='name'):
        ...

Or by their type (e.g. if they are admin) with :tl:`ChannelParticipantsFilter`:

.. code-block:: python

    from telethon.tl.types import ChannelParticipantsAdmins

    for user in client.iter_participants(chat, filter=ChannelParticipantsAdmins):
        ...


Open Conversations and Joined Channels
**************************************

The conversations you have open and the channels you have joined
are in your "dialogs", so to get them you need to `client.get_dialogs
<telethon.client.dialogs.DialogMethods.get_dialogs>`:

.. code-block:: python

    dialogs = client.get_dialogs()
    first = dialogs[0]
    print(first.title)

You can then use the dialog as if it were a peer:

.. code-block:: python

    client.send_message(first, 'hi')


You can access `dialog.draft <telethon.tl.custom.draft.Draft>` or you can
get them all at once without getting the dialogs:

.. code-block:: python

    drafts = client.get_drafts()


Downloading Media
*****************

It's easy to `download_profile_photo
<telethon.client.downloads.DownloadMethods.download_profile_photo>`:

.. code-block:: python

    client.download_profile_photo(user)

Or `download_media <telethon.client.downloads.DownloadMethods.download_media>`
from a message:

.. code-block:: python

    client.download_media(message)
    client.download_media(message, filename)
    # or
    message.download_media()
    message.download_media(filename)

Remember that these methods return the final filename where the
media was downloaded (e.g. it may add the extension automatically).

Getting Messages
****************

You can easily iterate over all the `messages
<telethon.tl.custom.message.Message>` of a chat with `iter_messages
<telethon.client.messages.MessageMethods.iter_messages>`:

.. code-block:: python

    for message in client.iter_messages(chat):
        ...  # do something with the message from recent to older

    for message in client.iter_messages(chat, reverse=True):
        ...  # going from the oldest to the most recent

You can also use it to search for messages from a specific person:

.. code-block:: python

    for message in client.iter_messages(chat, from_user='me'):
        ...

Or you can search by text:

.. code-block:: python

    for message in client.iter_messages(chat, search='hello'):
        ...

Or you can search by media with a :tl:`MessagesFilter`:

.. code-block:: python

    from telethon.tl.types import InputMessagesFilterPhotos

    for message in client.iter_messages(chat, filter=InputMessagesFilterPhotos):
        ...

If you want a list instead, use the get variant. The second
argument is the limit, and ``None`` means "get them all":

.. code-block:: python


    from telethon.tl.types import InputMessagesFilterPhotos

    # Get 0 photos and print the total
    photos = client.get_messages(chat, 0, filter=InputMessagesFilterPhotos)
    print(photos.total)

    # Get all the photos
    photos = client.get_messages(chat, None, filter=InputMessagesFilterPhotos)

Or just some IDs:

.. code-block:: python

    message_1337 = client.get_messages(chats, ids=1337)


Sending Messages
****************

Just use `send_message <telethon.client.messages.MessageMethods.send_message>`:

.. code-block:: python

    client.send_message('lonami', 'Thanks for the Telethon library!')

The function returns the `custom.Message <telethon.tl.custom.message.Message>`
that was sent so you can do more things with it if you want.

You can also `reply <telethon.tl.custom.message.Message.reply>` or
`respond <telethon.tl.custom.message.Message.respond>` to messages:

.. code-block:: python

    message.reply('Hello')
    message.respond('World')

Sending Markdown or HTML messages
*********************************

Markdown (``'md'`` or ``'markdown'``) is the default `parse_mode
<telethon.client.messageparse.MessageParseMethods.parse_mode>`
for the client. You can change the default parse mode like so:

.. code-block:: python

    client.parse_mode = 'html'


Now all messages will be formatted as HTML by default:

.. code-block:: python

    client.send_message('me', 'Some <b>bold</b> and <i>italic</i> text')
    client.send_message('me', 'An <a href="https://example.com">URL</a>')
    client.send_message('me', '<code>code</code> and <pre>pre\nblocks</pre>')
    client.send_message('me', '<a href="tg://user?id=me">Mentions</a>')


You can override the default parse mode to use for special cases:

.. code-block:: python

    # No parse mode by default
    client.parse_mode = None

    # ...but here I want markdown
    client.send_message('me', 'Hello, **world**!', parse_mode='md')

    # ...and here I need HTML
    client.send_message('me', 'Hello, <i>world</i>!', parse_mode='html')

The rules are the same as for Bot API, so please refer to
https://core.telegram.org/bots/api#formatting-options.

Sending Messages with Media
***************************

Sending media can be done with `send_file
<telethon.client.uploads.UploadMethods.send_file>`:

.. code-block:: python

    client.send_file(chat, '/my/photos/me.jpg', caption="It's me!")
    # or
    client.send_message(chat, "It's me!", file='/my/photos/me.jpg')

You can send voice notes or round videos by setting the right arguments:

.. code-block:: python

    client.send_file(chat, '/my/songs/song.mp3', voice_note=True)
    client.send_file(chat, '/my/videos/video.mp4', video_note=True)

You can set a JPG thumbnail for any document:

.. code-block:: python

    client.send_file(chat, '/my/documents/doc.txt', thumb='photo.jpg')

You can force sending images as documents:

.. code-block:: python

    client.send_file(chat, '/my/photos/photo.png', force_document=True)

You can send albums if you pass more than one file:

.. code-block:: python

    client.send_file(chat, [
        '/my/photos/holiday1.jpg',
        '/my/photos/holiday2.jpg',
        '/my/drawings/portrait.png'
    ])

The caption can also be a list to match the different photos.

Sending Messages with Buttons
*****************************

You must sign in as a bot in order to add inline buttons (or normal
keyboards) to your messages. Once you have signed in as a bot specify
the `Button <telethon.tl.custom.button.Button>` or buttons to use:

.. code-block:: python

    from telethon.tl.custom import Button

    async def callback(event):
        await event.edit('Thank you!')

    client.send_message(chat, 'Hello!',
                        buttons=Button.inline('Click me', callback))


You can also add the event handler yourself, or change the data payload:

.. code-block:: python

    from telethon import events

    @client.on(events.CallbackQuery)
    async def handler(event):
        await event.answer('You clicked {}!'.format(event.data))

    client.send_message(chat, 'Pick one', buttons=[
        [Button.inline('Left'), Button.inline('Right')],
        [Button.url('Check my site!', 'https://lonamiwebs.github.io')]
    ])

You can also use normal buttons (not inline) to request the user's
location, phone number, or simply for them to easily send a message:

.. code-block:: python

    client.send_message(chat, 'Welcome', buttons=[
        Button.text('Thanks!'),
        Button.request_phone('Send phone'),
        Button.request_location('Send location')
    ])

Forcing a reply or removing the keyboard can also be done:

.. code-block:: python

    client.send_message(chat, 'Reply to me', buttons=Button.force_reply())
    client.send_message(chat, 'Bye Keyboard!', buttons=Button.clear())

Remember to check `Button <telethon.tl.custom.button.Button>` for more.

Making Inline Queries
*********************

You can send messages ``via @bot`` by first making an inline query:

.. code-block:: python

    results = client.inline_query('like', 'Do you like Telethon?')

Then access the result you want and `click
<telethon.tl.custom.inlineresult.InlineResult.click>` it in the chat
where you want to send it to:

.. code-block:: python

    message = results[0].click('TelethonOffTopic')

Sending messages through inline bots lets you use buttons as a normal user.

It can look a bit strange at first, but you can make inline queries in no
chat in particular, and then click a *result* to send it to some chat.

Clicking Buttons
****************

Let's `click <telethon.tl.custom.message.Message.click>`
the message we sent in the example above!

.. code-block:: python

    message.click(0)

This will click the first button in the message. You could also
``click(row, column)``, using some text such as ``click(text='👍')``
or even the data directly ``click(data=b'payload')``.

Answering Inline Queries
************************

As a bot, you can answer to inline queries with `events.InlineQuery
<telethon.events.inlinequery.InlineQuery>`. You should make use of the
`builder <telethon.tl.custom.inlinebuilder.InlineBuilder>` property
to conveniently build the list of results to show to the user. Remember
to check the properties of the `InlineQuery.Event
<telethon.events.inlinequery.InlineQuery.Event>`:

.. code-block:: python

    @bot.on(events.InlineQuery)
    async def handler(event):
        builder = event.builder

        rev_text = event.text[::-1]
        await event.answer([
            builder.article('Reverse text', text=rev_text),
            builder.photo('/path/to/photo.jpg')
        ])

Conversations: Waiting for Messages or Replies
**********************************************

This one is really useful for unit testing your bots, which you can
even write within Telethon itself! You can open a `Conversation
<telethon.tl.custom.conversation.Conversation>` in any chat as:

.. code-block:: python

    with client.conversation(chat) as conv:
        ...

Conversations let you program a finite state machine with the
higher-level constructs we are all used to, such as ``while``
and ``if`` conditionals instead setting the state and jumping
from one place to another which is less clean.

For instance, let's imagine ``you`` are the bot talking to ``usr``:

.. code-block:: text

    <you> Hi!
    <usr> Hello!
    <you> Please tell me your name
    <usr> ?
    <you> Your name didn't have any letters! Try again
    <usr> Lonami
    <you> Thanks Lonami!

This can be programmed as follows:

.. code-block:: python

    with bot.conversation(chat) as conv:
        conv.send_message('Hi!')
        hello = conv.get_response()

        conv.send_message('Please tell me your name')
        name = conv.get_response().raw_text
        while not any(x.isalpha() for x in name):
            conv.send_message("Your name didn't have any letters! Try again")
            name = conv.get_response().raw_text

        conv.send_message('Thanks {}!'.format(name))

Note how we sent a message **with the conversation**, not with the client.
This is important so the conversation remembers what messages you sent.

The method reference for getting a response, getting a reply or marking
the conversation as read can be found by clicking here: `Conversation
<telethon.tl.custom.conversation.Conversation>`.

Sending a message or getting a response returns a `Message
<telethon.tl.custom.message.Message>`. Reading its documentation
will also be really useful!

If a reply never arrives or too many messages come in, getting
responses will raise ``asyncio.TimeoutError`` or ``ValueError``
respectively. You may want to ``except`` these and tell the user
they were too slow, or simply drop the conversation.


Forwarding Messages
*******************

You can forward up to 100 messages with `forward_messages
<telethon.client.messages.MessageMethods.forward_messages>`,
or a single one if you have the message with `forward_to
<telethon.tl.custom.message.Message.forward_to>`:

.. code-block:: python

    # a single one
    client.forward_messages(chat, message)
    # or
    client.forward_messages(chat, message_id, from_chat)
    # or
    message.forward_to(chat)

    # multiple
    client.forward_messages(chat, messages)
    # or
    client.forward_messages(chat, message_ids, from_chat)

You can also "forward" messages without showing "Forwarded from" by
re-sending the message:

.. code-block:: python

    client.send_message(chat, message)


Editing Messages
****************

With `edit_message <telethon.client.messages.MessageMethods.edit_message>`
or  `message.edit <telethon.tl.custom.message.Message.edit>`:

.. code-block:: python

    client.edit_message(message, 'New text')
    # or
    message.edit('New text')
    # or
    client.edit_message(chat, message_id, 'New text')

Deleting Messages
*****************

With `delete_messages <telethon.client.messages.MessageMethods.delete_messages>`
or  `message.delete <telethon.tl.custom.message.Message.delete>`. Note that the
first one supports deleting entire chats at once!:

.. code-block:: python

    client.delete_messages(chat, messages)
    # or
    message.delete()


Marking Messages as Read
************************

Marking messages up to a certain point as read with `send_read_acknowledge
<telethon.client.messages.MessageMethods.send_read_acknowledge>`:

.. code-block:: python

    client.send_read_acknowledge(last_message)
    # or
    client.send_read_acknowledge(last_message_id)
    # or
    client.send_read_acknowledge(messages)


Getting Entities
****************

Entities are users, chats, or channels. You can get them by their ID if
you have seen them before (e.g. you probably need to get all dialogs or
all the members from a chat first):

.. code-block:: python

    from telethon import utils

    me = client.get_entity('me')
    print(utils.get_display_name(me))

    chat = client.get_input_entity('username')
    for message in client.iter_messages(chat):
        ...

    # Note that you could have used the username directly, but it's
    # good to use get_input_entity if you will reuse it a lot.
    for message in client.iter_messages('username'):
        ...

    some_id = client.get_peer_id('+34123456789')

The documentation for shown methods are `get_entity
<telethon.client.users.UserMethods.get_entity>`, `get_input_entity
<telethon.client.users.UserMethods.get_input_entity>` and `get_peer_id
<telethon.client.users.UserMethods.get_peer_id>`.

Note that the utils package also has a `get_peer_id
<telethon.utils.get_peer_id>` but it won't work with things
that need access to the network such as usernames or phones,
which need to be in your contact list.
