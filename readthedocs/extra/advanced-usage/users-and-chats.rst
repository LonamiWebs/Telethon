=========================
Users and Chats
=========================

.. note::
    Make sure you have gone through :ref:`prelude` already!

.. contents::
    :depth: 2

.. _retrieving-an-entity:

Retrieving an entity (user or group)
**************************************
An “entity” is used to refer to either an `User`__ or a `Chat`__
(which includes a `Channel`__). The most straightforward way to get
an entity is to use ``TelegramClient.get_entity()``. This method accepts
either a string, which can be a username, phone number or `t.me`__-like
link, or an integer that will be the ID of an **user**. You can use it
like so:

    .. code-block:: python

        # all of these work
        lonami  = client.get_entity('lonami')
        lonami  = client.get_entity('t.me/lonami')
        lonami  = client.get_entity('https://telegram.dog/lonami')

        # other kind of entities
        channel = client.get_entity('telegram.me/joinchat/AAAAAEkk2WdoDrB4-Q8-gg')
        contact = client.get_entity('+34xxxxxxxxx')
        friend  = client.get_entity(friend_id)

For the last one to work, the library must have “seen” the user at least
once. The library will “see” the user as long as any request contains
them, so if you’ve called ``.get_dialogs()`` for instance, and your
friend was there, the library will know about them. For more, read about
the :ref:`sessions`.

If you want to get a channel or chat by ID, you need to specify that
they are a channel or a chat. The library can’t infer what they are by
just their ID (unless the ID is marked, but this is only done
internally), so you need to wrap the ID around a `Peer`__ object:

    .. code-block:: python

        from telethon.tl.types import PeerUser, PeerChat, PeerChannel
        my_user    = client.get_entity(PeerUser(some_id))
        my_chat    = client.get_entity(PeerChat(some_id))
        my_channel = client.get_entity(PeerChannel(some_id))

**Note** that most requests don’t ask for an ``User``, or a ``Chat``,
but rather for ``InputUser``, ``InputChat``, and so on. If this is the
case, you should prefer ``.get_input_entity()`` over ``.get_entity()``,
as it will be immediate if you provide an ID (whereas ``.get_entity()``
may need to find who the entity is first).

Via your open “chats” (dialogs)
-------------------------------

.. note::
    Please read here: :ref:`retrieving-all-dialogs`.

Via ResolveUsernameRequest
--------------------------

This is the request used by ``.get_entity`` internally, but you can also
use it by hand:

.. code-block:: python

    from telethon.tl.functions.contacts import ResolveUsernameRequest

    result = client(ResolveUsernameRequest('username'))
    found_chats = result.chats
    found_users = result.users
    # result.peer may be a PeerUser, PeerChat or PeerChannel

See `Peer`__ for more information about this result.

Via MessageFwdHeader
--------------------

If all you have is a `MessageFwdHeader`__ after you retrieved a bunch
of messages, this gives you access to the ``from_id`` (if forwarded from
an user) and ``channel_id`` (if forwarded from a channel). Invoking
`GetMessagesRequest`__ also returns a list of ``chats`` and
``users``, and you can find the desired entity there:

    .. code-block:: python

        # Logic to retrieve messages with `GetMessagesRequest´
        messages = foo()
        fwd_header = bar()

        user = next(u for u in messages.users if u.id == fwd_header.from_id)
        channel = next(c for c in messages.chats if c.id == fwd_header.channel_id)

Or you can just call ``.get_entity()`` with the ID, as you should have
seen that user or channel before. A call to ``GetMessagesRequest`` may
still be neeed.

Via GetContactsRequest
----------------------

The library will call this for you if you pass a phone number to
``.get_entity``, but again, it can be done manually. If the user you
want to talk to is a contact, you can use `GetContactsRequest`__:

    .. code-block:: python

        from telethon.tl.functions.contacts import GetContactsRequest
        from telethon.tl.types.contacts import Contacts

        contacts = client(GetContactsRequest(0))
        if isinstance(contacts, Contacts):
            users = contacts.users
            contacts = contacts.contacts

__ https://lonamiwebs.github.io/Telethon/types/user.html
__ https://lonamiwebs.github.io/Telethon/types/chat.html
__ https://lonamiwebs.github.io/Telethon/constructors/channel.html
__ https://t.me
__ https://lonamiwebs.github.io/Telethon/types/peer.html
__ https://lonamiwebs.github.io/Telethon/types/peer.html
__ https://lonamiwebs.github.io/Telethon/constructors/message_fwd_header.html
__ https://lonamiwebs.github.io/Telethon/methods/messages/get_messages.html
__ https://lonamiwebs.github.io/Telethon/methods/contacts/get_contacts.html


.. _retrieving-all-dialogs:

Retrieving all dialogs
***********************

There are several ``offset_xyz=`` parameters that have no effect at all,
but there's not much one can do since this is something the server should handle.
Currently, the only way to get all dialogs
(open chats, conversations, etc.) is by using the ``offset_date``:

    .. code-block:: python

        from telethon.tl.functions.messages import GetDialogsRequest
        from telethon.tl.types import InputPeerEmpty
        from time import sleep

        dialogs = []
        users = []
        chats = []

        last_date = None
        chunk_size = 20
        while True:
            result = client(GetDialogsRequest(
                         offset_date=last_date,
                         offset_id=0,
                         offset_peer=InputPeerEmpty(),
                         limit=chunk_size
                     ))
            dialogs.extend(result.dialogs)
            users.extend(result.users)
            chats.extend(result.chats)
            if not result.messages:
                break
            last_date = min(msg.date for msg in result.messages)
            sleep(2)


Joining a chat or channel
*******************************

Note that `Chat`__\ s are normal groups, and `Channel`__\ s are a
special form of `Chat`__\ s,
which can also be super-groups if their ``megagroup`` member is
``True``.

Joining a public channel
------------------------

Once you have the :ref:`entity <retrieving-an-entity>`
of the channel you want to join to, you can
make use of the `JoinChannelRequest`__ to join such channel:

    .. code-block:: python

        from telethon.tl.functions.channels import JoinChannelRequest
        client(JoinChannelRequest(channel))

        # In the same way, you can also leave such channel
        from telethon.tl.functions.channels import LeaveChannelRequest
        client(LeaveChannelRequest(input_channel))

For more on channels, check the `channels namespace`__.

Joining a private chat or channel
---------------------------------

If all you have is a link like this one:
``https://t.me/joinchat/AAAAAFFszQPyPEZ7wgxLtd``, you already have
enough information to join! The part after the
``https://t.me/joinchat/``, this is, ``AAAAAFFszQPyPEZ7wgxLtd`` on this
example, is the ``hash`` of the chat or channel. Now you can use
`ImportChatInviteRequest`__ as follows:

    .. -block:: python

        from telethon.tl.functions.messages import ImportChatInviteRequest
        updates = client(ImportChatInviteRequest('AAAAAEHbEkejzxUjAUCfYg'))

Adding someone else to such chat or channel
-------------------------------------------

If you don’t want to add yourself, maybe because you’re already in, you
can always add someone else with the `AddChatUserRequest`__, which
use is very straightforward:

    .. code-block:: python

        from telethon.tl.functions.messages import AddChatUserRequest

        client(AddChatUserRequest(
            chat_id,
            user_to_add,
            fwd_limit=10  # allow the user to see the 10 last messages
        ))

Checking a link without joining
-------------------------------

If you don’t need to join but rather check whether it’s a group or a
channel, you can use the `CheckChatInviteRequest`__, which takes in
the `hash`__ of said channel or group.

__ https://lonamiwebs.github.io/Telethon/constructors/chat.html
__ https://lonamiwebs.github.io/Telethon/constructors/channel.html
__ https://lonamiwebs.github.io/Telethon/types/chat.html
__ https://lonamiwebs.github.io/Telethon/methods/channels/join_channel.html
__ https://lonamiwebs.github.io/Telethon/methods/channels/index.html
__ https://lonamiwebs.github.io/Telethon/methods/messages/import_chat_invite.html
__ https://lonamiwebs.github.io/Telethon/methods/messages/add_chat_user.html
__ https://lonamiwebs.github.io/Telethon/methods/messages/check_chat_invite.html
__ https://github.com/LonamiWebs/Telethon/wiki/Joining-a-chat-or-channel#joining-a-private-chat-or-channel


Retrieving all chat members (channels too)
******************************************

In order to get all the members from a mega-group or channel, you need
to use `GetParticipantsRequest`__. As we can see it needs an
`InputChannel`__, (passing the mega-group or channel you’re going to
use will work), and a mandatory `ChannelParticipantsFilter`__. The
closest thing to “no filter” is to simply use
`ChannelParticipantsSearch`__ with an empty ``'q'`` string.

If we want to get *all* the members, we need to use a moving offset and
a fixed limit:

    .. code-block:: python

        from telethon.tl.functions.channels import GetParticipantsRequest
        from telethon.tl.types import ChannelParticipantsSearch
        from time import sleep

        offset = 0
        limit = 100
        all_participants = []

        while True:
            participants = client.invoke(GetParticipantsRequest(
                channel, ChannelParticipantsSearch(''), offset, limit
            ))
            if not participants.users:
                break
            all_participants.extend(participants.users)
            offset += len(participants.users)
            # sleep(1)  # This line seems to be optional, no guarantees!

Note that ``GetParticipantsRequest`` returns `ChannelParticipants`__,
which may have more information you need (like the role of the
participants, total count of members, etc.)

__ https://lonamiwebs.github.io/Telethon/methods/channels/get_participants.html
__ https://lonamiwebs.github.io/Telethon/methods/channels/get_participants.html
__ https://lonamiwebs.github.io/Telethon/types/channel_participants_filter.html
__ https://lonamiwebs.github.io/Telethon/constructors/channel_participants_search.html
__ https://lonamiwebs.github.io/Telethon/constructors/channels/channel_participants.html


Recent Actions
********************

“Recent actions” is simply the name official applications have given to
the “admin log”. Simply use `GetAdminLogRequest`__ for that, and
you’ll get AdminLogResults.events in return which in turn has the final
`.action`__.

__ https://lonamiwebs.github.io/Telethon/methods/channels/get_admin_log.html
__ https://lonamiwebs.github.io/Telethon/types/channel_admin_log_event_action.html


Increasing View Count in a Channel
****************************************

It has been asked `quite`__ `a few`__ `times`__ (really, `many`__), and
while I don’t understand why so many people ask this, the solution is to
use `GetMessagesViewsRequest`__, setting ``increment=True``:

    .. code-block:: python


        # Obtain `channel' through dialogs or through client.get_entity() or anyhow.
        # Obtain `msg_ids' through `.get_message_history()` or anyhow. Must be a list.

        client(GetMessagesViewsRequest(
            peer=channel,
            id=msg_ids,
            increment=True
        ))

__ https://github.com/LonamiWebs/Telethon/issues/233
__ https://github.com/LonamiWebs/Telethon/issues/305
__ https://github.com/LonamiWebs/Telethon/issues/409
__ https://github.com/LonamiWebs/Telethon/issues/447
__ https://lonamiwebs.github.io/Telethon/methods/messages/get_messages_views.html