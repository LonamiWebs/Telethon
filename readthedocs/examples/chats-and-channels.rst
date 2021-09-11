===============================
Working with Chats and Channels
===============================


.. note::

    These examples assume you have read :ref:`full-api`.

.. contents::


Joining a chat or channel
=========================

Note that :tl:`Chat` are normal groups, and :tl:`Channel` are a
special form of :tl:`Chat`, which can also be super-groups if
their ``megagroup`` member is `True`.


Joining a public channel
========================

Once you have the :ref:`entity <entities>` of the channel you want to join
to, you can make use of the :tl:`JoinChannelRequest` to join such channel:

.. code-block:: python

    from telethon.tl.functions.channels import JoinChannelRequest
    await client(JoinChannelRequest(channel))

    # In the same way, you can also leave such channel
    from telethon.tl.functions.channels import LeaveChannelRequest
    await client(LeaveChannelRequest(input_channel))


For more on channels, check the `channels namespace`__.


__ https://tl.telethon.dev/methods/channels/index.html


Joining a private chat or channel
=================================

If all you have is a link like this one:
``https://t.me/joinchat/AAAAAFFszQPyPEZ7wgxLtd``, you already have
enough information to join! The part after the
``https://t.me/joinchat/``, this is, ``AAAAAFFszQPyPEZ7wgxLtd`` on this
example, is the ``hash`` of the chat or channel. Now you can use
:tl:`ImportChatInviteRequest` as follows:

.. code-block:: python

    from telethon.tl.functions.messages import ImportChatInviteRequest
    updates = await client(ImportChatInviteRequest('AAAAAEHbEkejzxUjAUCfYg'))


Adding someone else to such chat or channel
===========================================

If you don't want to add yourself, maybe because you're already in,
you can always add someone else with the :tl:`AddChatUserRequest`, which
use is very straightforward, or :tl:`InviteToChannelRequest` for channels:

.. code-block:: python

    # For normal chats
    from telethon.tl.functions.messages import AddChatUserRequest

    # Note that ``user_to_add`` is NOT the name of the parameter.
    # It's the user you want to add (``user_id=user_to_add``).
    await client(AddChatUserRequest(
        chat_id,
        user_to_add,
        fwd_limit=10  # Allow the user to see the 10 last messages
    ))

    # For channels (which includes megagroups)
    from telethon.tl.functions.channels import InviteToChannelRequest

    await client(InviteToChannelRequest(
        channel,
        [users_to_add]
    ))

Note that this method will only really work for friends or bot accounts.
Trying to mass-add users with this approach will not work, and can put both
your account and group to risk, possibly being flagged as spam and limited.


Checking a link without joining
===============================

If you don't need to join but rather check whether it's a group or a
channel, you can use the :tl:`CheckChatInviteRequest`, which takes in
the hash of said channel or group.


Increasing View Count in a Channel
==================================

It has been asked `quite`__ `a few`__ `times`__ (really, `many`__), and
while I don't understand why so many people ask this, the solution is to
use :tl:`GetMessagesViewsRequest`, setting ``increment=True``:

.. code-block:: python


    # Obtain `channel' through dialogs or through client.get_entity() or anyhow.
    # Obtain `msg_ids' through `.get_messages()` or anyhow. Must be a list.

    await client(GetMessagesViewsRequest(
        peer=channel,
        id=msg_ids,
        increment=True
    ))


Note that you can only do this **once or twice a day** per account,
running this in a loop will obviously not increase the views forever
unless you wait a day between each iteration. If you run it any sooner
than that, the views simply won't be increased.

__ https://github.com/LonamiWebs/Telethon/issues/233
__ https://github.com/LonamiWebs/Telethon/issues/305
__ https://github.com/LonamiWebs/Telethon/issues/409
__ https://github.com/LonamiWebs/Telethon/issues/447
