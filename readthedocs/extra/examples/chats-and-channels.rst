===============================
Working with Chats and Channels
===============================


.. note::

    These examples assume you have read :ref:`accessing-the-full-api`.


Joining a chat or channel
*************************

Note that `Chat`__\ s are normal groups, and `Channel`__\ s are a
special form of `Chat`__\ s,
which can also be super-groups if their ``megagroup`` member is
``True``.


Joining a public channel
************************

Once you have the :ref:`entity <entities>` of the channel you want to join
to, you can make use of the `JoinChannelRequest`__ to join such channel:

    .. code-block:: python

        from telethon.tl.functions.channels import JoinChannelRequest
        client(JoinChannelRequest(channel))

        # In the same way, you can also leave such channel
        from telethon.tl.functions.channels import LeaveChannelRequest
        client(LeaveChannelRequest(input_channel))


For more on channels, check the `channels namespace`__.


Joining a private chat or channel
*********************************

If all you have is a link like this one:
``https://t.me/joinchat/AAAAAFFszQPyPEZ7wgxLtd``, you already have
enough information to join! The part after the
``https://t.me/joinchat/``, this is, ``AAAAAFFszQPyPEZ7wgxLtd`` on this
example, is the ``hash`` of the chat or channel. Now you can use
`ImportChatInviteRequest`__ as follows:

    .. code-block:: python

        from telethon.tl.functions.messages import ImportChatInviteRequest
        updates = client(ImportChatInviteRequest('AAAAAEHbEkejzxUjAUCfYg'))


Adding someone else to such chat or channel
*******************************************

If you don't want to add yourself, maybe because you're already in,
you can always add someone else with the `AddChatUserRequest`__,
which use is very straightforward:

    .. code-block:: python

        from telethon.tl.functions.messages import AddChatUserRequest

        client(AddChatUserRequest(
            chat_id,
            user_to_add,
            fwd_limit=10  # Allow the user to see the 10 last messages
        ))


Checking a link without joining
*******************************

If you don't need to join but rather check whether it's a group or a
channel, you can use the `CheckChatInviteRequest`__, which takes in
the hash of said channel or group.

__ https://lonamiwebs.github.io/Telethon/constructors/chat.html
__ https://lonamiwebs.github.io/Telethon/constructors/channel.html
__ https://lonamiwebs.github.io/Telethon/types/chat.html
__ https://lonamiwebs.github.io/Telethon/methods/channels/join_channel.html
__ https://lonamiwebs.github.io/Telethon/methods/channels/index.html
__ https://lonamiwebs.github.io/Telethon/methods/messages/import_chat_invite.html
__ https://lonamiwebs.github.io/Telethon/methods/messages/add_chat_user.html
__ https://lonamiwebs.github.io/Telethon/methods/messages/check_chat_invite.html


Retrieving all chat members (channels too)
******************************************

In order to get all the members from a mega-group or channel, you need
to use `GetParticipantsRequest`__. As we can see it needs an
`InputChannel`__, (passing the mega-group or channel you're going to
use will work), and a mandatory `ChannelParticipantsFilter`__. The
closest thing to "no filter" is to simply use
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
            participants = client(GetParticipantsRequest(
                channel, ChannelParticipantsSearch(''), offset, limit,
                hash=0
            ))
            if not participants.users:
                break
            all_participants.extend(participants.users)
            offset += len(participants.users)


Note that ``GetParticipantsRequest`` returns `ChannelParticipants`__,
which may have more information you need (like the role of the
participants, total count of members, etc.)

__ https://lonamiwebs.github.io/Telethon/methods/channels/get_participants.html
__ https://lonamiwebs.github.io/Telethon/methods/channels/get_participants.html
__ https://lonamiwebs.github.io/Telethon/types/channel_participants_filter.html
__ https://lonamiwebs.github.io/Telethon/constructors/channel_participants_search.html
__ https://lonamiwebs.github.io/Telethon/constructors/channels/channel_participants.html


Recent Actions
**************

"Recent actions" is simply the name official applications have given to
the "admin log". Simply use `GetAdminLogRequest`__ for that, and
you'll get AdminLogResults.events in return which in turn has the final
`.action`__.

__ https://lonamiwebs.github.io/Telethon/methods/channels/get_admin_log.html
__ https://lonamiwebs.github.io/Telethon/types/channel_admin_log_event_action.html


Admin Permissions
*****************

Giving or revoking admin permissions can be done with the `EditAdminRequest`__:

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
        
|  Thanks to `@Kyle2142`__ for `pointing out`__ that you **cannot** set all
|  parameters to ``True`` to give a user full permissions, as not all
|  permissions are related to both broadcast channels/megagroups.
|
|  E.g. trying to set ``post_messages=True`` in a megagroup will raise an
|  error. It is recommended to always use keyword arguments, and to set only
|  the permissions the user needs. If you don't need to change a permission,
|  it can be omitted (full list `here`__).

__ https://lonamiwebs.github.io/Telethon/methods/channels/edit_admin.html
__ https://github.com/Kyle2142
__ https://github.com/LonamiWebs/Telethon/issues/490
__ https://lonamiwebs.github.io/Telethon/constructors/channel_admin_rights.html


Increasing View Count in a Channel
**********************************

It has been asked `quite`__ `a few`__ `times`__ (really, `many`__), and
while I don't understand why so many people ask this, the solution is to
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
