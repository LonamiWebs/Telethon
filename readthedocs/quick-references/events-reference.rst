================
Events Reference
================

Here you will find a quick summary of all the methods
and properties that you can access when working with events.

You can access the client that creates this event by doing
``event.client``, and you should view the description of the
events to find out what arguments it allows on creation and
its **attributes** (the properties will be shown here).

It is important to remember that **all events subclass**
`ChatGetter <telethon.tl.custom.chatgetter.ChatGetter>`!

.. contents::


ChatGetter
==========

All events subclass `ChatGetter <telethon.tl.custom.chatgetter.ChatGetter>`,
which means all events have (and you can access to):

.. currentmodule:: telethon.tl.custom.chatgetter.ChatGetter

.. autosummary::
    :nosignatures:

    chat
    input_chat
    chat_id
    is_private
    is_group
    is_channel

    get_chat
    get_input_chat


CallbackQuery
=============

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


ChatAction
==========

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


InlineQuery
===========

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


MessageDeleted
==============

Full documentation for the `MessageDeleted
<telethon.events.messagedeleted.MessageDeleted>`.

It only has the ``deleted_id`` and ``deleted_ids`` attributes
(in addition to the chat if the deletion happened in a channel).


MessageEdited
=============

Full documentation for the `MessageEdited
<telethon.events.messageedited.MessageEdited>`.

This event is the same as `NewMessage
<telethon.events.newmessage.NewMessage>`,
but occurs only when an edit happens.


MessageRead
===========

Full documentation for the `MessageRead
<telethon.events.messageread.MessageRead>`.

.. currentmodule:: telethon.events.messageread.MessageRead.Event

.. autosummary::
    :nosignatures:

        inbox
        message_ids

        get_messages
        is_read


NewMessage
==========

Full documentation for the `NewMessage
<telethon.events.newmessage.NewMessage>`.

Note that the new message event **should be treated as** a
normal `Message <telethon.tl.custom.message.Message>`, with
the following exceptions:

* ``pattern_match`` is the match object returned by ``pattern=``.
* ``message`` is **not** the message string. It's the `Message
  <telethon.tl.custom.message.Message>` object.

Remember, this event is just a proxy over the message, so while
you won't see its attributes and properties, you can still access
them.


Raw
===

Raw events are not actual events. Instead, they are the raw
:tl:`Update` object that Telegram sends. You normally shouldn't
need these.


UserUpdate
==========

Full documentation for the `UserUpdate
<telethon.events.userupdate.UserUpdate>`.

A lot of fields are attributes and not properties, so they
are not shown here.

.. currentmodule:: telethon.events.userupdate.UserUpdate.Event

.. autosummary::
    :nosignatures:

        user
        input_user
        user_id

        get_user
        get_input_user
