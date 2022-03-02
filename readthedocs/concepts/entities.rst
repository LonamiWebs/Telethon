.. _entities:

===============
Users and Chats
===============

The library widely uses the concept of "users" to refer to both real accounts
and bot accounts, as well as the concept of "chats" to refer to groups and
broadcast channels.

The most general term you can use to think about these is "an entity", but
recent versions of the library often prefer to opt for names which better
reflect the intention, such as "dialog" when a previously-existing
conversation is expected, or "profile" when referring to the information about
the user or chat.

.. note::

    When something "dialog-like" is required, it means that you need to
    provide something that can be used to refer to an open conversation.
    These things include, but are not limited to, packed chats, usernames,
    integer IDs (identifiers), :tl:`Peer` objects, or even entire :tl:`User`,
    :tl:`Chat` and :tl:`Channel` objects and even phone numbers **from people
    you have in your contact list**.

    To "encounter" an ID, you would have to "find it" like you would in the
    normal app. If the peer is in your dialogs, you would need to
    `client.get_dialogs() <telethon.client.dialogs.DialogMethods.get_dialogs>`.
    If the peer is someone in a group, you would similarly
    `client.get_participants(group) <telethon.client.chats.ChatMethods.get_participants>`.

    Once you have encountered an ID, the library will (by default) have saved
    its packed version for you, which is needed to invoke most methods.
    This is why sometimes you might encounter this error when working with
    the library. You should ``except ValueError`` and run code that you know
    should work to find the user or chat. You **cannot** use an ID of someone
    you haven't interacted with. Because this is more unreliable, packed chats
    are recommended instead.


.. contents::


What is a User?
===============

A `User <telethon.types._custom.user.User>` can be either a real user account
(some person who has signed up for an account) or a bot account which is
programmed to perform certain actions (created by a developer via
`@BotFather <https://t.me/BotFather>`_).

A lot of methods and requests require user or chats to work. For example,
you can send a message to a *user*, ban a *user* from a group, and so on.
These methods accept more than just `User <telethon.types._custom.user.User>`
as the input parameter. You can also use packed users, usernames, string phone
numbers, or integer IDs, although some have higher cost than others.

When using the username, the library must fetch it first, which can be
expensive. When using the phone number, the library must fetch it first, which
can be expensive. If you plan to use these, it's recommended you manually use
`client.get_profile() <telethon.client.users.UserMethods.get_profile>` to cache
the username or phone number, and then use the value returned instead.

.. note::

    Remember that the phone number must be in your contact list before you
    can use it.

The recommended type to use as input parameters to the methods is either a
`User <telethon.types._custom.user.User>` instance or its packed type.

In the raw API, users are instances of :tl:`User` (or :tl:`UserEmpty`), which
are returned in response to some requests, such as :tl:`GetUsersRequest`.
There are also variants for use as "input parameters", such as :tl:`InputUser`
and :tl:`InputPeerUser`. You generally **do not need** to worry about these
types unless you're using raw API.


What is a Chat?
===============

A `Chat <telethon.types._custom.chat.Chat>` can be a small group chat (the
default group type created by users where many users can join and talk), a
megagroup (also known as "supergroup"), a broadcast channel or a broadcast
group.

The term "chat" is really overloaded in Telegram. The library tries to be
explicit and always use "small group chat", "megagroup" and "broadcast" to
differentiate. However, Telegram's API uses "chat" to refer to both "chat"
(small group chat), and "channel" (megagroup, broadcast or "gigagroup" which
is a broadcast group of type channel).

A lot of methods and requests require a chat to work. For example,
you can get the participants from a *chat*, kick users from a *chat*, and so on.
These methods accept more than just `Chat <telethon.types._custom.chat.Chat>`
as the input parameter. You can also use packed chats, the public link, or
integer IDs, although some have higher cost than others.

When using the public link, the library must fetch it first, which can be
expensive. If you plan to use these, it's recommended you manually use
`client.get_profile() <telethon.client.users.UserMethods.get_profile>` to cache
the link, and then use the value returned instead.

.. note::

    The link of a public chat has the form "t.me/username", where the username
    can belong to either an actual user or a public chat.

The recommended type to use as input parameters to the methods is either a
`Chat <telethon.types._custom.chat.Chat>` instance or its packed type.

In the raw API, chats are instances of :tl:`Chat` and :tl:`Channel` (or
:tl:`ChatEmpty`, :tl:`ChatForbidden` and :tl:`ChannelForbidden`), which
are returned in response to some requests, such as :tl:`messages.GetChats`
and :tl:`channels.GetChannels`. There are also variants for use as "input
parameters", such as :tl:`InputChannel` and :tl:`InputPeerChannel`. You
generally **do not need** to worry about these types unless you're using raw API.


When to use each term?
======================

The term "dialog" is used when the library expects a reference to an open
conversation (from the list the user sees when they open the application).

The term "profile" is used instead of "dialog" when the conversation is not
expected to exist. Because "dialog" is more specific than "profile", "dialog"
is used where possible instead.

In general, you should not use named arguments for neither "dialogs" or
"profiles", since they're the first argument. The parameter name only exists
for documentation purposes.

The term "chat" is used where a group or broadcast channel is expected. This
includes small groups, megagroups, broadcast channels and broadcast groups.
Telegram's API has, in the past, made a difference between which methods can
be used for "small group chats" and everything else. For example, small group
chats cannot have a public link (they automatically convert to megagroups).
Group permissions also used to be different, but because Telegram may unify
these eventually, the library attempts to hide this distinction. In general,
this is not something you should worry about.


Fetching profile information
============================

Through the use of the :ref:`sessions`, the library will automatically
remember the packed users and chats, along with some extra information,
so you're able to just do this:

.. code-block:: python

    # (These examples assume you are inside an "async def")
    #
    # Dialogs are the "conversations you have open".
    # This method returns a list of Dialog, which
    # has the .user and .chat attributes (among others).
    #
    # This part is IMPORTANT, because it fills the cache.
    dialogs = await client.get_dialogs()

    # All of these work and do the same, but are more expensive to use.
    channel = await client.get_profile('username')
    channel = await client.get_profile('t.me/username')
    channel = await client.get_profile('https://telegram.dog/username')
    contact = await client.get_profile('+34xxxxxxxxx')

    # This will work, but only if the ID is in cache.
    friend = await client.get_profile(friend_id)

    # This is the most reliable way to fetch a profile.
    user = await client.get_profile('U.123.456789')
    group = await client.get_profile('G.456.0')
    broadcast = await client.get_profile('C.789.123456')


All methods in the :ref:`telethon-client` accept any of the above
prior to sending the request to save you from the hassle of doing so manually.
That way, convenience calls such as `client.send_message('username', 'hi!')
<telethon.client.messages.MessageMethods.send_message>` become possible.
However, it can be expensive to fetch the username every time, so this is
better left for things which are not executed often.

Although it's explicitly noted in the documentation that messages
*subclass* `ChatGetter <telethon.tl.custom.chatgetter.ChatGetter>`
and `SenderGetter <telethon.tl.custom.sendergetter.SenderGetter>`,
this section will explain what this means.

When the documentation says "Bases: `telethon.tl.custom.chatgetter.ChatGetter`"
it means that the class you're looking at, *also* can act as the class it
bases. In this case, `ChatGetter <telethon.tl.custom.chatgetter.ChatGetter>`
knows how to get the *chat* where a thing belongs to.

So, a `Message <telethon.tl.custom.message.Message>` is a
`ChatGetter <telethon.tl.custom.chatgetter.ChatGetter>`.
That means you can do this:

.. code-block:: python

    message.chat_id
    message.chat
    await event.get_chat()
    # ...etc

`SenderGetter <telethon.tl.custom.sendergetter.SenderGetter>` is similar:

.. code-block:: python

    message.user_id
    message.user
    await event.get_input_user()
    # ...etc

Quite a few things implement them, so it makes sense to reuse the code.
For example, all events (except raw updates) implement `ChatGetter
<telethon.tl.custom.chatgetter.ChatGetter>` since all events occur
in some chat.


Packed User and packed Chat
===========================

A packed `User <telethon.types._custom.user.User>` or a packed
`Chat <telethon.types._custom.chat.Chat>` can be thought of as
"a small string reference to the actual user or chat".

It can easily be saved or embedded in the code for later use,
without having to worry if the user is in the session file cache.

This "packed representation" is a compact way to store the type of the User
or Chat (is it a user account, a bot, a broadcast channel…), the identifier,
and the access hash. This "access hash" is something Telegram uses to ensure
that you can actually use this "User" or "Chat" in requests (so you can't just
create some random user identifier and expect it to work).

In the raw API, this is pretty much "input peers", but the library uses the
term "packed user or chat" to refer to its custom type and string
representation.

The User and Chat IDs are the same for all user and bot accounts. However, the
access hash is **different for each account**, so trying to reuse the access
hash from one account in another will **not** work. This also means the packed
representation will only work for the account that created it.

The library needs to have this access hash in some way for it to work.
If it only has an ID and this ID is not in cache, it will not work.
If using the packed representation, the hash is embedded, and will always work.

Every method, including raw API, will automatically convert your types to the
expected input type the API uses, meaning the following will work:


.. code-block:: python

    await client(_tl.fn.messages.SendMessage('username', 'hello'))

(This is only a raw API example, there are better ways to send messages.)


Summary
=======

TL;DR; If you're here because of *"Could not find the input peer for"*,
you must ask yourself, "how did I find this user or chat through official
applications"? Now do the same with the library. Use what applies:

.. code-block:: python

    # (These examples assume you are inside an "async def")
    async with client:
        # Does it have a username? Use it!
        user = await client.get_profile(username)

        # Do you have a conversation open with them? Get dialogs.
        await client.get_dialogs()

        # Are they participants of some group? Get them.
        await client.get_participants('username')

        # Is the user the original sender of a forwarded message? Fetch the message.
        await client.get_messages('username', 100)

        # NOW you can use the ID anywhere!
        await client.send_message(123456, 'Hi!')

        user = await client.get_profile(123456)
        print(user)

Once the library has "seen" the user or chat, you can use their **integer** ID.
You can't use users or chats from IDs the library hasn't seen. You must make
the library see them *at least once* and disconnect properly. You know where
the user or chat are, and you must tell the library. It won't guess for you.

This is why it's recommended to use the packed versions instead. They will
always work (unless Telegram, for some very unlikely reason, changes the way
using users and chats works, of course).
