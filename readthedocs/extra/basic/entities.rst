=========================
Users, Chats and Channels
=========================


Introduction
************

The library widely uses the concept of "entities". An entity will refer
to any ``User``, ``Chat`` or ``Channel`` object that the API may return
in response to certain methods, such as ``GetUsersRequest``.

Getting entities
****************

Through the use of the :ref:`sessions`, the library will automatically
remember the ID and hash pair, along with some extra information, so
you're able to just do this:

    .. code-block:: python

        # Dialogs are the "conversations you have open".
        # This method returns a list of Dialog, which
        # has the .entity attribute and other information.
        dialogs = client.get_dialogs(limit=200)

        # All of these work and do the same.
        lonami = client.get_entity('lonami')
        lonami = client.get_entity('t.me/lonami')
        lonami = client.get_entity('https://telegram.dog/lonami')

        # Other kind of entities.
        channel = client.get_entity('telegram.me/joinchat/AAAAAEkk2WdoDrB4-Q8-gg')
        contact = client.get_entity('+34xxxxxxxxx')
        friend  = client.get_entity(friend_id)

        # Using Peer/InputPeer (note that the API may return these)
        # users, chats and channels may all have the same ID, so it's
        # necessary to wrap (at least) chat and channels inside Peer.
        from telethon.tl.types import PeerUser, PeerChat, PeerChannel
        my_user    = client.get_entity(PeerUser(some_id))
        my_chat    = client.get_entity(PeerChat(some_id))
        my_channel = client.get_entity(PeerChannel(some_id))


All methods in the :ref:`telegram-client` call ``.get_input_entity()`` to
further save you from the hassle of doing so manually, so doing things like
``client.send_message('lonami', 'hi!')`` is possible.

Every entity the library "sees" (in any response to any call) will by
default be cached in the ``.session`` file, to avoid performing
unnecessary API calls. If the entity cannot be found, some calls
like ``ResolveUsernameRequest`` or ``GetContactsRequest`` may be
made to obtain the required information.


Entities vs. Input Entities
***************************

.. note::

    Don't worry if you don't understand this section, just remember some
    of the details listed here are important. When you're calling a method,
    don't call ``.get_entity()`` before, just use the username or phone,
    or the entity retrieved by other means like ``.get_dialogs()``.


To save bandwidth, the API also makes use of their "input" versions.
The input version of an entity (e.g. ``InputPeerUser``, ``InputChat``,
etc.) only contains the minimum required information that's required
for Telegram to be able to identify who you're referring to: their ID
and hash. This ID/hash pair is unique per user, so if you use the pair
given by another user **or bot** it will **not** work.

To save *even more* bandwidth, the API also makes use of the ``Peer``
versions, which just have an ID. This serves to identify them, but
peers alone are not enough to use them. You need to know their hash
before you can "use them".

As we just mentioned, API calls don't need to know the whole information
about the entities, only their ID and hash. For this reason, another method,
``.get_input_entity()`` is available. This will always use the cache while
possible, making zero API calls most of the time. When a request is made,
if you provided the full entity, e.g. an ``User``, the library will convert
it to the required ``InputPeer`` automatically for you.

**You should always favour** ``.get_input_entity()`` **over** ``.get_entity()``
for this reason! Calling the latter will always make an API call to get
the most recent information about said entity, but invoking requests don't
need this information, just the ``InputPeer``. Only use ``.get_entity()``
if you need to get actual information, like the username, name, title, etc.
of the entity.

To further simplify the workflow, since the version ``0.16.2`` of the
library, the raw requests you make to the API are also able to call
``.get_input_entity`` wherever needed, so you can even do things like:

    .. code-block:: python

        client(SendMessageRequest('username', 'hello'))

The library will call the ``.resolve()`` method of the request, which will
resolve ``'username'`` with the appropriated ``InputPeer``. Don't worry if
you don't get this yet, but remember some of the details here are important.
