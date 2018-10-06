.. _entities:

=========================
Users, Chats and Channels
=========================


.. important::

    TL;DR; If you're here because of *"Could not find the input entity for"*,
    you must ask yourself "how did I find this entity through official
    applications"? Now do the same with the library. Use what applies:

    .. code-block:: python

        with client:
            # Does it have an username? Use it!
            entity = client.get_entity(username)

            # Do you have a conversation open with them? Get dialogs.
            client.get_dialogs()

            # Are they participant of some group? Get them.
            client.get_participants('TelethonChat')

            # Is the entity the original sender of a forwarded message? Get it.
            client.get_messages('TelethonChat', 100)

            # NOW you can use the ID, anywhere!
            entity = client.get_entity(123456)
            client.send_message(123456, 'Hi!')

    Once the library has "seen" the entity, you can use their **integer** ID.
    You can't use entities from IDs the library hasn't seen. You must make the
    library see them *at least once* and disconnect properly. You know where
    the entities are and you must tell the library. It won't guess for you.


.. contents::


Introduction
************

The library widely uses the concept of "entities". An entity will refer
to any :tl:`User`, :tl:`Chat` or :tl:`Channel` object that the API may return
in response to certain methods, such as :tl:`GetUsersRequest`.

.. note::

    When something "entity-like" is required, it means that you need to
    provide something that can be turned into an entity. These things include,
    but are not limited to, usernames, exact titles, IDs, :tl:`Peer` objects,
    or even entire :tl:`User`, :tl:`Chat` and :tl:`Channel` objects and even
    phone numbers from people you have in your contacts.

    To "encounter" an ID, you would have to "find it" like you would in the
    normal app. If the peer is in your dialogs, you would need to
    `client.get_dialogs() <telethon.client.dialogs.DialogMethods.get_dialogs>`.
    If the peer is someone in a group, you would similarly
    `client.get_participants(group) <telethon.client.chats.ChatMethods.get_participants>`.

    Once you have encountered an ID, the library will (by default) have saved
    their ``access_hash`` for you, which is needed to invoke most methods.
    This is why sometimes you might encounter this error when working with
    the library. You should ``except ValueError`` and run code that you know
    should work to find the entity.


Getting entities
****************

Through the use of the :ref:`sessions`, the library will automatically
remember the ID and hash pair, along with some extra information, so
you're able to just do this:

.. code-block:: python

    # Dialogs are the "conversations you have open".
    # This method returns a list of Dialog, which
    # has the .entity attribute and other information.
    dialogs = client.get_dialogs()

    # All of these work and do the same.
    lonami = client.get_entity('lonami')
    lonami = client.get_entity('t.me/lonami')
    lonami = client.get_entity('https://telegram.dog/lonami')

    # Other kind of entities.
    channel = client.get_entity('telegram.me/joinchat/AAAAAEkk2WdoDrB4-Q8-gg')
    contact = client.get_entity('+34xxxxxxxxx')
    friend  = client.get_entity(friend_id)

    # Getting entities through their ID (User, Chat or Channel)
    entity = client.get_entity(some_id)

    # You can be more explicit about the type for said ID by wrapping
    # it inside a Peer instance. This is recommended but not necessary.
    from telethon.tl.types import PeerUser, PeerChat, PeerChannel

    my_user    = client.get_entity(PeerUser(some_id))
    my_chat    = client.get_entity(PeerChat(some_id))
    my_channel = client.get_entity(PeerChannel(some_id))


.. note::

    You **don't** need to get the entity before using it! Just let
    the library do its job. Use the phone, username, ID or input
    entity (preferred but not necessary), whatever you already have.

All methods in the :ref:`telegram-client` call `.get_input_entity()
<telethon.client.users.UserMethods.get_input_entity>` prior
to sending the requst to save you from the hassle of doing so manually.
That way, convenience calls such as `client.send_message('lonami', 'hi!')
<telethon.client.messages.MessageMethods.send_message>`
become possible.

Every entity the library encounters (in any response to any call) will by
default be cached in the ``.session`` file (an SQLite database), to avoid
performing unnecessary API calls. If the entity cannot be found, additonal
calls like :tl:`ResolveUsernameRequest` or :tl:`GetContactsRequest` may be
made to obtain the required information.


Entities vs. Input Entities
***************************

.. note::

    Don't worry if you don't understand this section, just remember some
    of the details listed here are important. When you're calling a method,
    don't call `client.get_entity() <telethon.client.users.UserMethods.get_entity>`
    beforehand, just use the username or phone, or the entity retrieved by
    other means like `client.get_dialogs()
    <telethon.client.dialogs.DialogMethods.get_dialogs>`.

On top of the normal types, the API also make use of what they call their
``Input*`` versions of objects. The input version of an entity (e.g.
:tl:`InputPeerUser`, :tl:`InputChat`, etc.) only contains the minimum
information that's required from Telegram to be able to identify
who you're referring to: a :tl:`Peer`'s **ID** and **hash**. They
are named like this because they are input parameters in the requests.

Entities' ID are the same for all user and bot accounts, however, the access
hash is **different for each account**, so trying to reuse the access hash
from one account in another will **not** work.

Sometimes, Telegram only needs to indicate the type of the entity along
with their ID. For this purpose, :tl:`Peer` versions of the entities also
exist, which just have the ID. You cannot get the hash out of them since
you should not be needing it. The library probably has cached it before.

Peers are enough to identify an entity, but they are not enough to make
a request with them use them. You need to know their hash before you can
"use them", and to know the hash you need to "encounter" them, let it
be in your dialogs, participants, message forwards, etc.

.. note::

    You *can* use peers with the library. Behind the scenes, they are
    replaced with the input variant. Peers "aren't enough" on their own
    but the library will do some more work to use the right type.

As we just mentioned, API calls don't need to know the whole information
about the entities, only their ID and hash. For this reason, another method,
`client.get_input_entity() <telethon.client.users.UserMethods.get_input_entity>`
is available. This will always use the cache while possible, making zero API
calls most of the time. When a request is made, if you provided the full
entity, e.g. an :tl:`User`, the library will convert it to the required
:tl:`InputPeer` automatically for you.

**You should always favour**
`client.get_input_entity() <telethon.client.users.UserMethods.get_input_entity>`
**over**
`client.get_entity() <telethon.client.users.UserMethods.get_entity>`
for this reason! Calling the latter will always make an API call to get
the most recent information about said entity, but invoking requests don't
need this information, just the :tl:`InputPeer`. Only use
`client.get_entity() <telethon.client.users.UserMethods.get_entity>`
if you need to get actual information, like the username, name, title, etc.
of the entity.

To further simplify the workflow, since the version ``0.16.2`` of the
library, the raw requests you make to the API are also able to call
`client.get_input_entity() <telethon.client.users.UserMethods.get_input_entity>`
wherever needed, so you can even do things like:

.. code-block:: python

    client(SendMessageRequest('username', 'hello'))

The library will call the ``.resolve()`` method of the request, which will
resolve ``'username'`` with the appropriated :tl:`InputPeer`. Don't worry if
you don't get this yet, but remember some of the details here are important.


Full entities
*************

In addition to :tl:`PeerUser`, :tl:`InputPeerUser`, :tl:`User` (and its
variants for chats and channels), there is also the concept of :tl:`UserFull`.

This full variant has additional information such as whether the user is
blocked, its notification settings, the bio or about of the user, etc.

There is also :tl:`messages.ChatFull` which is the equivalent of full entities
for chats and channels, with also the about section of the channel. Note that
the ``users`` field only contains bots for the channel (so that clients can
suggest commands to use).

You can get both of these by invoking :tl:`GetFullUser`, :tl:`GetFullChat`
and :tl:`GetFullChannel` respectively.
