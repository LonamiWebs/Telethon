.. _chats-channels:

=================
Chats vs Channels
=================

Telegram's raw API can get very confusing sometimes, in particular when it
comes to talking about "chats", "channels", "groups", "megagroups", and all
those concepts.

This section will try to explain what each of these concepts are.


Chats
=====

A ``Chat`` can be used to talk about either the common "subclass" that both
chats and channels share, or the concrete :tl:`Chat` type.

Technically, both :tl:`Chat` and :tl:`Channel` are a form of the `Chat type`_.

**Most of the time**, the term :tl:`Chat` is used to talk about *small group
chats*. When you create a group through an official application, this is the
type that you get. Official applications refer to these as "Group".

Both the bot API and Telethon will add a minus sign (negate) the real chat ID
so that you can tell at a glance, with just a number, the entity type.

For example, if you create a chat with :tl:`CreateChatRequest`, the real chat
ID might be something like `123`. If you try printing it from a
`message.chat_id` you will see `-123`. This ID helps Telethon know you're
talking about a :tl:`Chat`.


Channels
========

Official applications create a *broadcast* channel when you create a new
channel (used to broadcast messages, only administrators can post messages).

Official applications implicitly *migrate* an *existing* :tl:`Chat` to a
*megagroup* :tl:`Channel` when you perform certain actions (exceed user limit,
add a public username, set certain permissions, etc.).

A ``Channel`` can be created directly with :tl:`CreateChannelRequest`, as
either a ``megagroup`` or ``broadcast``.

Official applications use the term "channel" **only** for broadcast channels.

The API refers to the different types of :tl:`Channel` with certain attributes:

* A **broadcast channel** is a :tl:`Channel` with the ``channel.broadcast``
  attribute set to `True`.

* A **megagroup channel** is a :tl:`Channel` with the ``channel.megagroup``
  attribute set to `True`. Official applications refer to this as "supergroup".

* A **gigagroup channel** is a :tl:`Channel` with the ``channel.gigagroup``
  attribute set to `True`. Official applications refer to this as "broadcast
  groups", and is used when a megagroup becomes very large and administrators
  want to transform it into something where only they can post messages.


Both the bot API and Telethon will "concatenate" ``-100`` to the real chat ID
so that you can tell at a glance, with just a number, the entity type.

For example, if you create a new broadcast channel, the real channel ID might
be something like `456`. If you try printing it from a `message.chat_id` you
will see `-1000000000456`. This ID helps Telethon know you're talking about a
:tl:`Channel`.


Converting IDs
==============

You can convert between the "marked" identifiers (prefixed with a minus sign)
and the real ones with ``utils.resolve_id``. It will return a tuple with the
real ID, and the peer type (the class):

.. code-block:: python

    from telethon import utils
    real_id, peer_type = utils.resolve_id(-1000000000456)

    print(real_id)  # 456
    print(peer_type)  # <class 'telethon.tl.types.PeerChannel'>

    peer = peer_type(real_id)
    print(peer)  # PeerChannel(channel_id=456)


The reverse operation can be done with ``utils.get_peer_id``:

.. code-block:: python

    print(utils.get_peer_id(types.PeerChannel(456)))  # -1000000000456


Note that this function can also work with other types, like :tl:`Chat` or
:tl:`Channel` instances.

If you need to convert other types like usernames which might need to perform
API calls to find out the identifier, you can use ``client.get_peer_id``:


.. code-block:: python

    print(await client.get_peer_id('me'))  # your id


If there is no "mark" (no minus sign), Telethon will assume your identifier
refers to a :tl:`User`. If this is **not** the case, you can manually fix it:


.. code-block:: python

    from telethon import types
    await client.send_message(types.PeerChannel(456), 'hello')
    #                         ^^^^^^^^^^^^^^^^^ explicit peer type


A note on raw API
=================

Certain methods only work on a :tl:`Chat`, and some others only work on a
:tl:`Channel` (and these may only work in broadcast, or megagroup). Your code
likely knows what it's working with, so it shouldn't be too much of an issue.

If you need to find the :tl:`Channel` from a :tl:`Chat` that migrated to it,
access the `migrated_to` property:

.. code-block:: python

    # chat is a Chat
    channel = await client.get_entity(chat.migrated_to)
    # channel is now a Channel

Channels do not have a "migrated_from", but a :tl:`ChannelFull` does. You can
use :tl:`GetFullChannelRequest` to obtain this:

.. code-block:: python

    from telethon import functions
    full = await client(functions.channels.GetFullChannelRequest(your_channel))
    full_channel = full.full_chat
    # full_channel is a ChannelFull
    print(full_channel.migrated_from_chat_id)

This way, you can also access the linked discussion megagroup of a broadcast channel:

.. code-block:: python

    print(full_channel.linked_chat_id)  # prints ID of linked discussion group or None

You do not need to use ``client.get_entity`` to access the
``migrated_from_chat_id`` :tl:`Chat` or the ``linked_chat_id`` :tl:`Channel`.
They are in the ``full.chats`` attribute:

.. code-block:: python

    if full_channel.migrated_from_chat_id:
        migrated_from_chat = next(c for c in full.chats if c.id == full_channel.migrated_from_chat_id)
        print(migrated_from_chat.title)

    if full_channel.linked_chat_id:
        linked_group = next(c for c in full.chats if c.id == full_channel.linked_chat_id)
        print(linked_group.username)

.. _Chat type: https://tl.telethon.dev/types/chat.html
