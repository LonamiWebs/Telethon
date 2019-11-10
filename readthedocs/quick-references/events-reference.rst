================
Events Reference
================

Here you will find a quick summary of all the methods
and properties that you can access when working with events.

You can access the client that creates this event by doing
``event.client``, and you should view the description of the
events to find out what arguments it allows on creation and
its **attributes** (the properties will be shown here).

.. important::

    Remember that **all events base** `ChatGetter
    <telethon.tl.custom.chatgetter.ChatGetter>`! Please see :ref:`faq`
    if you don't know what this means or the implications of it.

.. contents::


NewMessage
==========

Occurs whenever a new text message or a message with media arrives.

.. note::

    The new message event **should be treated as** a
    normal `Message <telethon.tl.custom.message.Message>`, with
    the following exceptions:

    * ``pattern_match`` is the match object returned by ``pattern=``.
    * ``message`` is **not** the message string. It's the `Message
      <telethon.tl.custom.message.Message>` object.

    Remember, this event is just a proxy over the message, so while
    you won't see its attributes and properties, you can still access
    them. Please see the full documentation for examples.

Full documentation for the `NewMessage
<telethon.events.newmessage.NewMessage>`.


MessageEdited
=============

Occurs whenever a message is edited. Just like `NewMessage
<telethon.events.newmessage.NewMessage>`, you should treat
this event as a `Message <telethon.tl.custom.message.Message>`.

Full documentation for the `MessageEdited
<telethon.events.messageedited.MessageEdited>`.


MessageDeleted
==============

Occurs whenever a message is deleted. Note that this event isn't 100%
reliable, since Telegram doesn't always notify the clients that a message
was deleted.

It only has the ``deleted_id`` and ``deleted_ids`` attributes
(in addition to the chat if the deletion happened in a channel).

Full documentation for the `MessageDeleted
<telethon.events.messagedeleted.MessageDeleted>`.


MessageRead
===========

Occurs whenever one or more messages are read in a chat.

Full documentation for the `MessageRead
<telethon.events.messageread.MessageRead>`.

.. currentmodule:: telethon.events.messageread.MessageRead.Event

.. autosummary::
    :nosignatures:

        inbox
        message_ids

        get_messages
        is_read


ChatAction
==========

Occurs on certain chat actions, such as chat title changes,
user join or leaves, pinned messages, photo changes, etc.

Full documentation for the `ChatAction
<telethon.events.chataction.ChatAction>`.

.. currentmodule:: telethon.events.chataction.ChatAction.Event

.. autosummary::
    :nosignatures:

        added_by
        kicked_by
        user
        input_user
        user_id
        users
        input_users
        user_ids

        respond
        reply
        delete
        get_pinned_message
        get_added_by
        get_kicked_by
        get_user
        get_input_user
        get_users
        get_input_users


UserUpdate
==========

Occurs whenever a user goes online, starts typing, etc.

Full documentation for the `UserUpdate
<telethon.events.userupdate.UserUpdate>`.

.. currentmodule:: telethon.events.userupdate.UserUpdate.Event

.. autosummary::
    :nosignatures:

        user
        input_user
        user_id

        get_user
        get_input_user

        typing
        uploading
        recording
        playing
        cancel
        geo
        audio
        round
        video
        contact
        document
        photo
        last_seen
        until
        online
        recently
        within_weeks
        within_months


CallbackQuery
=============

Occurs whenever you sign in as a bot and a user
clicks one of the inline buttons on your messages.

Full documentation for the `CallbackQuery
<telethon.events.callbackquery.CallbackQuery>`.

.. currentmodule:: telethon.events.callbackquery.CallbackQuery.Event

.. autosummary::
    :nosignatures:

        id
        message_id
        data
        chat_instance
        via_inline

        respond
        reply
        edit
        delete
        answer
        get_message

InlineQuery
===========

Occurs whenever you sign in as a bot and a user
sends an inline query such as ``@bot query``.

Full documentation for the `InlineQuery
<telethon.events.inlinequery.InlineQuery>`.

.. currentmodule:: telethon.events.inlinequery.InlineQuery.Event

.. autosummary::
    :nosignatures:

        id
        text
        offset
        geo
        builder

        answer

Album
=====

Occurs whenever you receive an entire album.

Full documentation for the `Album
<telethon.events.album.Album>`.

.. currentmodule:: telethon.events.album.Album.Event

.. autosummary::
    :nosignatures:

        grouped_id
        text
        raw_text
        is_reply
        forward

        get_reply_message
        respond
        reply
        forward_to
        edit
        delete
        mark_read
        pin

Raw
===

Raw events are not actual events. Instead, they are the raw
:tl:`Update` object that Telegram sends. You normally shouldn't
need these.
