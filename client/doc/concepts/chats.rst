Chats
=====

.. currentmodule:: telethon

The term :term:`chat` is extremely overloaded, so it's no surprise many are confused by what it means.
This section should hopefully clear that up.


Telethon Chat
-------------

The word :term:`chat` in Telethon is used to refer a place where messages are sent to.
Therefore, a Telethon :term:`chat` can be another user, a bot, a group, or a broadcast channel.
All of those are places where messages can be sent.

Of course, chats do more things than contain messages.
They often have a name, username, photo, description, and other information.

When a :term:`chat` appears in a parameter or as a property,
it means that it will be either a :class:`~types.User`, :class:`~types.Group` or :class:`~types.Channel`.

When a parameter must be "chat-like", it means Telethon will accept anything that can be "converted" to a :term:`chat`.
The following types are chat-like:

* The ``'me'`` literal string. This represents the account that is logged in ("yourself").
* An ``'@username'``. The at-sign ``@`` is optional. Note that links are not supported.
* An ``'+1 23'`` phone number string. It must be an ``str`` and start with the plus-sign ``+`` character.
* An ``123`` integer identifier. It must be an ``int`` and cannot be negative.
* An existing :class:`~types.User`, :class:`~types.Group` or :class:`~types.Channel`.
* A :class:`~types.PackedChat`.

Previous versions of Telethon referred to this term as "entity" or "entities" instead.


Telegram Chat
-------------

The Telegram API is very confusing when it comes to the word "chat".
You only need to know about this if you plan to use the :term:`Raw API`.

In the schema definitions, there are two boxed types, :tl:`User` and :tl:`Chat`.
A boxed :tl:`User` can only be the bare :tl:`user`, but the boxed :tl:`Chat` can be either a bare :tl:`chat` or a bare :tl:`channel`.

A bare :tl:`chat` always refers to small groups.
A bare :tl:`channel` can have either the ``broadcast`` or the ``megagroup`` flag set to :data:`True`.

A bare :tl:`channel` with the ``broadcast`` flag set to :data:`True` is known as a broadcast channel.
A bare :tl:`channel` with the ``megagroup`` flag set to :data:`True` is known as a supergroup.

A bare :tl:`chat` with has less features than a bare :tl:`channel` ``megagroup``.
Official clients are very good at hiding this difference.
They will implicitly convert bare :tl:`chat` to bare :tl:`channel` ``megagroup`` when doing certain operations.
Doing things like setting a username is actually a two-step process (migration followed by updating the username).
Official clients transparently merge the history of migrated :tl:`channel` with their old :tl:`chat`.

In Telethon:

* A :class:`~types.User` always corresponds to :tl:`user`.
* A :class:`~types.Group` represents either a :tl:`chat` or a :tl:`channel` ``megagroup``.
* A :class:`~types.Channel` represents a :tl:`channel` ``broadcast``.

Telethon classes aim to map to similar concepts in official applications.


Bot API chat
------------

The Bot API follows a certain convention when it comes to identifiers:

* User IDs are positive.
* Chat IDs are negative.
* Channel IDs are prefixed with ``-100``.

Telethon encourages the use of :class:`~types.PackedChat` instead of naked identifiers.
As a reminder, negative identifiers are not supported in Telethon's chat-like parameters.


Encountering chats
------------------

The way you encounter chats in Telethon is no different from official clients.
If you:

* …have joined a group or channel, or have sent private messages to some user, you can :meth:`~Client.get_dialogs`.
* …know the user is in your contact list, you can :meth:`~Client.get_contacts`.
* …know the user has a common chat with you, you can :meth:`~Client.get_participants` of the chat in common.
* …know the username of the user, group, or channel, you can :meth:`~Client.resolve_username`.
* …are a bot responding to users, you will be able to access the :attr:`types.Message.sender`.

Chats access hash
-----------------

Users, supergroups and channels all need an :term:`access hash`.

In Telethon, the :class:`~types.PackedChat` is the recommended way to deal with the identifier-hash pairs.
This compact type can be used anywhere a chat is expected.
It's designed to be easy to store and cache in any way your application chooses.

Bot accounts can get away with an invalid :term:`access hash` for certain operations under certain conditions.
The same is true for user accounts, although to a lesser extent.

When using just the identifier to refer to a chat, Telethon will attempt to retrieve its hash from its in-memory cache.
If this fails, an invalid hash will be used. This may or may not make the API call succeed.
For this reason, it is recommended that you always use :class:`~types.PackedChat` instead.

Remember that an :term:`access hash` is account-bound.
You cannot obtain an :term:`access hash` in Account-A and use it in Account-B.
