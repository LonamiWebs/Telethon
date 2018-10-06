===============================
Working with Chats and Channels
===============================


.. note::

    These examples assume you have read :ref:`accessing-the-full-api`.

.. contents::


Joining a chat or channel
*************************

Note that :tl:`Chat` are normal groups, and :tl:`Channel` are a
special form of :tl:`Chat`, which can also be super-groups if
their ``megagroup`` member is ``True``.


Joining a public channel
************************

Once you have the :ref:`entity <entities>` of the channel you want to join
to, you can make use of the :tl:`JoinChannelRequest` to join such channel:

.. code-block:: python

    from telethon.tl.functions.channels import JoinChannelRequest
    client(JoinChannelRequest(channel))

    # In the same way, you can also leave such channel
    from telethon.tl.functions.channels import LeaveChannelRequest
    client(LeaveChannelRequest(input_channel))


For more on channels, check the `channels namespace`__.


__ https://lonamiwebs.github.io/Telethon/methods/channels/index.html


Joining a private chat or channel
*********************************

If all you have is a link like this one:
``https://t.me/joinchat/AAAAAFFszQPyPEZ7wgxLtd``, you already have
enough information to join! The part after the
``https://t.me/joinchat/``, this is, ``AAAAAFFszQPyPEZ7wgxLtd`` on this
example, is the ``hash`` of the chat or channel. Now you can use
:tl:`ImportChatInviteRequest` as follows:

.. code-block:: python

    from telethon.tl.functions.messages import ImportChatInviteRequest
    updates = client(ImportChatInviteRequest('AAAAAEHbEkejzxUjAUCfYg'))


Adding someone else to such chat or channel
*******************************************

If you don't want to add yourself, maybe because you're already in,
you can always add someone else with the :tl:`AddChatUserRequest`, which
use is very straightforward, or :tl:`InviteToChannelRequest` for channels:

.. code-block:: python

    # For normal chats
    from telethon.tl.functions.messages import AddChatUserRequest

    # Note that ``user_to_add`` is NOT the name of the parameter.
    # It's the user you want to add (``user_id=user_to_add``).
    client(AddChatUserRequest(
        chat_id,
        user_to_add,
        fwd_limit=10  # Allow the user to see the 10 last messages
    ))

    # For channels (which includes megagroups)
    from telethon.tl.functions.channels import InviteToChannelRequest

    client(InviteToChannelRequest(
        channel,
        [users_to_add]
    ))


Checking a link without joining
*******************************

If you don't need to join but rather check whether it's a group or a
channel, you can use the :tl:`CheckChatInviteRequest`, which takes in
the hash of said channel or group.


Retrieving all chat members (channels too)
******************************************

.. note::

    Use the `telethon.telegram_client.TelegramClient.iter_participants`
    friendly method instead unless you have a better reason not to!

    This method will handle different chat types for you automatically.


Here is the easy way to do it:

.. code-block:: python

    participants = client.get_participants(group)

Now we will show how the method works internally.

In order to get all the members from a mega-group or channel, you need
to use :tl:`GetParticipantsRequest`. As we can see it needs an
:tl:`InputChannel`, (passing the mega-group or channel you're going to
use will work), and a mandatory :tl:`ChannelParticipantsFilter`. The
closest thing to "no filter" is to simply use
:tl:`ChannelParticipantsSearch` with an empty ``'q'`` string.

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
        participants = client(GetParticipantsRequest(
            channel, ChannelParticipantsSearch(''), offset, limit, hash=0
        ))
        if not participants.users:
            break
        all_participants.extend(participants.users)
        offset += len(participants.users)


.. note::

    If you need more than 10,000 members from a group you should use the
    mentioned ``client.get_participants(..., aggressive=True)``. It will
    do some tricks behind the scenes to get as many entities as possible.
    Refer to `issue 573`__ for more on this.


Note that :tl:`GetParticipantsRequest` returns :tl:`ChannelParticipants`,
which may have more information you need (like the role of the
participants, total count of members, etc.)

__ https://github.com/LonamiWebs/Telethon/issues/573


Recent Actions
**************

"Recent actions" is simply the name official applications have given to
the "admin log". Simply use :tl:`GetAdminLogRequest` for that, and
you'll get AdminLogResults.events in return which in turn has the final
`.action`__.

__ https://lonamiwebs.github.io/Telethon/types/channel_admin_log_event_action.html


Admin Permissions
*****************

Giving or revoking admin permissions can be done with the :tl:`EditAdminRequest`:

.. code-block:: python

    from telethon.tl.functions.channels import EditAdminRequest
    from telethon.tl.types import ChannelAdminRights

    # You need both the channel and who to grant permissions
    # They can either be channel/user or input channel/input user.
    #
    # ChannelAdminRights is a list of granted permissions.
    # Set to True those you want to give.
    rights = ChannelAdminRights(
        post_messages=None,
        add_admins=None,
        invite_users=None,
        change_info=True,
        ban_users=None,
        delete_messages=True,
        pin_messages=True,
        invite_link=None,
        edit_messages=None
    )
    # Equivalent to:
    #     rights = ChannelAdminRights(
    #         change_info=True,
    #         delete_messages=True,
    #         pin_messages=True
    #     )

    # Once you have a ChannelAdminRights, invoke it
    client(EditAdminRequest(channel, user, rights))

    # User will now be able to change group info, delete other people's
    # messages and pin messages.


.. note::

    Thanks to `@Kyle2142`__ for `pointing out`__ that you **cannot** set all
    parameters to ``True`` to give a user full permissions, as not all
    permissions are related to both broadcast channels/megagroups.

    E.g. trying to set ``post_messages=True`` in a megagroup will raise an
    error. It is recommended to always use keyword arguments, and to set only
    the permissions the user needs. If you don't need to change a permission,
    it can be omitted (full list `here`__).


Restricting Users
*****************

Similar to how you give or revoke admin permissions, you can edit the
banned rights of a user through :tl:`EditBannedRequest` and its parameter
:tl:`ChannelBannedRights`:

.. code-block:: python

    from telethon.tl.functions.channels import EditBannedRequest
    from telethon.tl.types import ChannelBannedRights

    from datetime import datetime, timedelta

    # Restricting a user for 7 days, only allowing view/send messages.
    #
    # Note that it's "reversed". You must set to ``True`` the permissions
    # you want to REMOVE, and leave as ``None`` those you want to KEEP.
    rights = ChannelBannedRights(
        until_date=timedelta(days=7),
        view_messages=None,
        send_messages=None,
        send_media=True,
        send_stickers=True,
        send_gifs=True,
        send_games=True,
        send_inline=True,
        embed_links=True
    )

    # The above is equivalent to
    rights = ChannelBannedRights(
        until_date=datetime.now() + timedelta(days=7),
        send_media=True,
        send_stickers=True,
        send_gifs=True,
        send_games=True,
        send_inline=True,
        embed_links=True
    )

    client(EditBannedRequest(channel, user, rights))


You can also use a ``datetime`` object for ``until_date=``, or even a
Unix timestamp. Note that if you ban someone for less than 30 seconds
or for more than 366 days, Telegram will consider the ban to actually
last forever. This is officially documented under
https://core.telegram.org/bots/api#restrictchatmember.


Kicking a member
****************

Telegram doesn't actually have a request to kick a user from a group.
Instead, you need to restrict them so they can't see messages. Any date
is enough:

.. code-block:: python

    from telethon.tl.functions.channels import EditBannedRequest
    from telethon.tl.types import ChannelBannedRights

    client(EditBannedRequest(
        channel, user, ChannelBannedRights(
            until_date=None,
            view_messages=True
        )
    ))


__ https://github.com/Kyle2142
__ https://github.com/LonamiWebs/Telethon/issues/490
__ https://lonamiwebs.github.io/Telethon/constructors/channel_admin_rights.html


Increasing View Count in a Channel
**********************************

It has been asked `quite`__ `a few`__ `times`__ (really, `many`__), and
while I don't understand why so many people ask this, the solution is to
use :tl:`GetMessagesViewsRequest`, setting ``increment=True``:

.. code-block:: python


    # Obtain `channel' through dialogs or through client.get_entity() or anyhow.
    # Obtain `msg_ids' through `.get_messages()` or anyhow. Must be a list.

    client(GetMessagesViewsRequest(
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
