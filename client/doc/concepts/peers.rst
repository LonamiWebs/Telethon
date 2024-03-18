Peers, users and chats
======================

.. currentmodule:: telethon

The term :term:`peer` may sound strange at first, but it's the best we have after much consideration.
This section aims to explain what peers are, and how they relate to users, group chats, and broadcast channels.


Telethon Peer
-------------

The :class:`~types.Peer` type in Telethon is the base class for :class:`~types.User`, :class:`~types.Group` and :class:`~types.Channel`.
Therefore, a Telethon ":term:`peer`" represents an entity with various attributes: identifier, username, photo, title, and other information depending on its type.

The :class:`~types.PeerRef` type represents a reference to a :class:`~types.Peer`, and can be obtained from its :attr:`~types.Peer.ref` attribute.
Each peer type has its own reference type, namely :class:`~types.UserRef`, :class:`~types.GroupRef` and :class:`~types.ChannelRef`.

| Most methods accept either the :class:`~types.Peer` or :class:`~types.PeerRef` (and their subclasses) as input.
  You do not need to fetch the full :class:`~types.Peer` to :meth:`~Client.get_messages` or :meth:`~Client.send_file`\ s— a :class:`~types.PeerRef` is enough.
| Some methods will only work on groups and channels (like :meth:`~Client.get_participants`), or users (like :meth:`~Client.inline_query`).

A Telethon "chat" refers to either groups and channels, or the place where messages are sent to.
In the latter case, the chat could also belong to a user, so it would be represented by a :class:`~types.Peer`.

A Telethon "group" is used to refer to either small group chats or supergroups.
This matches what the interface of official applications call these entities.

A Telethon "user" is used to refer to either user accounts or bot accounts.
This matches Telegram's API, as both are represented by the same user object.


Telegram Peer
-------------

.. note::

    This section is mainly of interest if you plan to use the :term:`Raw API`.

Telegram uses :tl:`Peer`\ s to categorize users, groups and channels, much like how Telethon does.
It also has the concept of :tl:`InputPeer`\ s, which are commonly used as input parameters when sending requests.
These match the concept of Telethon's peer references.

The main confusion in Telegram's API comes from the word "chat".

In the :term:`TL` schema definitions, there are two boxed types, :tl:`User` and :tl:`Chat`.
A boxed :tl:`User` can only be the bare :tl:`user`, but the boxed :tl:`Chat` can be either a bare :tl:`chat` or a bare :tl:`channel`.

A bare :tl:`chat` always refers to small groups.
A bare :tl:`channel` can have either the ``broadcast`` or the ``megagroup`` flag set to :data:`True`.

A bare :tl:`channel` with the ``broadcast`` flag set to :data:`True` is known as a broadcast channel.
A bare :tl:`channel` with the ``megagroup`` flag set to :data:`True` is known as a supergroup.

A bare :tl:`chat` has less features available than a bare :tl:`channel` ``megagroup``.
Official clients are very good at hiding this difference.
They will implicitly convert bare :tl:`chat` to bare :tl:`channel` ``megagroup`` when doing certain operations.
Doing things like setting a username is actually a two-step process (migration followed by updating the username).
Official clients transparently merge the history of migrated :tl:`channel` with their old :tl:`chat`.

In Telethon:

* A :class:`~types.User` always corresponds to :tl:`user`.
* A :class:`~types.Group` represents either a :tl:`chat` or a :tl:`channel` ``megagroup``.
* A :class:`~types.Channel` represents a :tl:`channel` ``broadcast``.

Telethon classes aim to map to similar concepts in official applications.


Bot API Peer
------------

The Bot API does not use the word "peer", but instead opts to use "chat" and "user" only, despite chats also being able to reference users.
The Bot API follows a certain convention when it comes to chat and user identifiers:

* User IDs are positive.
* Chat IDs are negative.
* Channel IDs are *also* negative, but are prefixed by ``-100``.

Telethon does not support Bot API's formatted identifiers, and instead expects you to create the appropriated :class:`~types.PeerRef`:

.. code-block:: python

    from telethon.types import UserRef, GroupRef, ChannelRef

    user = UserRef(123)  # user_id 123 from bot API becomes 123
    group = GroupRef(456)  # chat_id -456 from bot API becomes 456
    channel = ChannelRef(789)  # chat_id -100789 from bot API becomes 789

While using a Telethon Client logged in to a bot account, the above may work for certain methods.
However, user accounts often require what's known as an "access hash", obtained by encountering the peer first.


Encountering peers
------------------

The way you encounter peers in Telethon is no different from official clients.
If you:

* …have joined a group or channel, or have sent private messages to some user, you can :meth:`~Client.get_dialogs`.
* …know the user is in your contact list, you can :meth:`~Client.get_contacts`.
* …know the user has a common chat with you, you can :meth:`~Client.get_participants` of the chat in common.
* …know the username of the user, group, or channel, you can :meth:`~Client.resolve_username`.
* …are a bot responding to users, you will be able to access the :attr:`types.Message.sender`.


Access hashes and authorizations
--------------------------------

Users, supergroups and channels all need an :term:`access hash`.
This value is proof that you're authorized to access the peer in question.
This value is also account-bound.
You cannot obtain an :term:`access hash` in Account-A and use it in Account-B.

In Telethon, the :class:`~types.PeerRef` is the recommended way to deal with the identifier-authorization pairs.
This compact type can be used anywhere a peer is expected.
It's designed to be easy to store and cache in any way your application chooses.
You can easily serialize it to a string and back via ``str(ref)`` and :meth:`types.PeerRef.from_str`.

Bot accounts can get away with an invalid :term:`access hash` for certain operations under certain conditions.
The same is true for user accounts, although to a lesser extent.
When you create a :class:`~types.PeerRef` without specifying an authorization, a bogus :term:`access hash` will be used.
