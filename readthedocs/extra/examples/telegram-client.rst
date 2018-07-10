========================
Examples with the Client
========================

This section explores the methods defined in the :ref:`telegram-client`
with some practical examples. The section assumes that you have imported
the ``telethon.sync`` package and that you have a client ready to use.

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

    client.download_profile_method(user)

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
    client.send_file(chat, '/my/videos/video.mp3', video_note=True)

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
