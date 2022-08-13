=========================
Version 2 Migration Guide
=========================

Version 2 represents the second major version change, breaking compatibility
with old code beyond the usual raw API changes in order to clean up a lot of
the technical debt that has grown on the project.

This document documents all the things you should be aware of when migrating from Telethon version
1.x to 2.0 onwards. It is sorted roughly from the "likely most impactful changes" to "there's a
good chance you were not relying on this to begin with".

**Please read this document in full before upgrading your code to Telethon 2.0.**


Python 3.5 is no longer supported
---------------------------------

The library will no longer attempt to support Python 3.5. The minimum version is now Python 3.7.

This also means workarounds for 3.6 and below have been dropped.


User, chat and channel identifiers are now 64-bit numbers
---------------------------------------------------------

`Layer 133 <https://diff.telethon.dev/?from=132&to=133>`__ changed *a lot* of identifiers from
``int`` to ``long``, meaning they will no longer fit in 32 bits, and instead require 64 bits.

If you were storing these identifiers somewhere size did matter (for example, a database), you
will need to migrate that to support the new size requirement of 8 bytes.

For the full list of types changed, please review the above link.


Peer IDs, including chat_id and sender_id, no longer follow bot API conventions
-------------------------------------------------------------------------------

Both the ``utils.get_peer_id`` and ``client.get_peer_id`` methods no longer have an ``add_mark``
parameter. Both will always return the original ID as given by Telegram. This should lead to less
confusion. However, it also means that an integer ID on its own no longer embeds the information
about the type (did it belong to a user, chat, or channel?), so ``utils.get_peer`` can no longer
guess the type from just a number.

Because it's not possible to know what other changes Telegram will do with identifiers, it's
probably best to get used to transparently storing whatever value they send along with the type
separatedly.

As far as I can tell, user, chat and channel identifiers are globally unique, meaning a channel
and a user cannot share the same identifier. The library currently makes this assumption. However,
this is merely an observation (I have never heard of such a collision exist), and Telegram could
change at any time. If you want to be on the safe side, you're encouraged to save a pair of type
and identifier, rather than just the number.

// TODO we DEFINITELY need to provide a way to "upgrade" old ids
// TODO and storing type+number by hand is a pain, provide better alternative
// TODO get_peer_id is gone now too!


Synchronous compatibility mode has been removed
-----------------------------------------------

The "sync hack" (which kicked in as soon as anything from ``telethon.sync`` was imported) has been
removed. This implies:

* The ``telethon.sync`` module is gone.
* Synchronous context-managers (``with`` as opposed to ``async with``) are no longer supported.
  Most notably, you can no longer do ``with client``. It must be ``async with client`` now.
* The "smart" behaviour of the following methods has been removed and now they no longer work in
  a synchronous context when the ``asyncio`` event loop was not running. This means they now need
  to be used with ``await`` (or, alternatively, manually used with ``loop.run_until_complete``):
  * ``start``
  * ``disconnect``
  * ``run_until_disconnected``

// TODO provide standalone alternative for this?


Overhaul of events and updates
------------------------------

Updates produced by the client are now also processed by your event handlers.
Before, if you had some code listening for new outgoing messages, only messages you sent with
another client, such as from Telegram Desktop, would be processed. Now, if your own code uses
``client.send_message``, you will also receive the new message event. Be careful, as this can
easily lead to "loops" (a new outgoing message can trigger ``client.send_message``, which
triggers a new outgoing message and the cycle repeats)!

There are no longer "event builders" and "event" types. Now there are only events, and you
register the type of events you want, not an instance. Because of this, the way filters are
specified have also changed:

.. code-block:: python

    # OLD
    @client.on(events.NewMessage(chats=...))
    async def handler(event):
        pass

    # NEW
    @client.on(events.NewMessage, chats=...)
    async def handler(event): # ^^         ^
        pass

This also means filters are unified, although not all filters have an effect on all events types.
Type hinting is now done through ``events.NewMessage`` and not ``events.NewMessage.Event``.

The filter rework also enables more features. For example, you can now mutate a ``chats`` filter
to add or remove a chat that needs to be received by a handler, rather than having to remove and
re-add the event handler.

The ``from_users`` filter has been renamed to ``senders``.

The ``inbox`` filter for ``events.MessageRead`` has been removed, in favour of ``outgoing`` and
``incoming``.

``events.register``, ``events.unregister`` and ``events.is_handler`` have been removed. There is
no longer anything special about methods which are handlers, and they are no longer monkey-patched.
Because pre-defining the event type to handle without a client was useful, you can now instead use
the following syntax:

.. code-block:: python

    # OLD
    @events.register(events.NewMessage)
    async def handler(event):
        pass

    # NEW
    async def handler(event: events.NewMessage):
        pass  #       ^^^^^^^^^^^^^^^^^^^^^^^^

As a bonus, you only need to type-hint once, and both your IDE and Telethon will understand what
you meant. This is similar to Python's ``@dataclass`` which uses type hints.

// TODO document filter creation and usage, showcase how to mutate them


Complete overhaul of session files
----------------------------------

If you were using third-party libraries to deal with sessions, you will need to wait for those to
be updated. The library will automatically upgrade the SQLite session files to the new version,
and the ``StringSession`` remains backward-compatible. The sessions can now be async.

In case you were relying on the tables used by SQLite (even though these should have been, and
will still need to be, treated as an implementation detail), here are the changes:

* The ``sessions`` table is now correctly split into ``datacenter`` and ``session``.
  ``datacenter`` contains information about a Telegram datacenter, along with its corresponding
  authorization key, and ``session`` contains information about the update state and user.
* The ``entities`` table is now called ``entity`` and stores the ``type`` separatedly.
* The ``update_state`` table is now split into ``session`` and ``channel``, which can contain
  a per-channel ``pts``.

Because **the new version does not cache usernames, phone numbers and display names**, using these
in method calls is now quite expensive. You *should* migrate your code to do the Right Thing and
start using identifiers rather than usernames, phone numbers or invite links. This is both simpler
and more reliable, because while a user identifier won't change, their username could.

You can use the following snippet to make a JSON backup (alternatively, you could just copy the
``.session`` file and keep it around) in case you want to preserve the cached usernames:

.. code-block:: python

    import sqlite, json
    with sqlite3.connect('your.session') as conn, open('entities.json', 'w', encoding='utf-8') as fp:
        json.dump([
            {'id': id, 'hash': hash, 'username': username, 'phone': phone, 'name': name, 'date': date}
            for (id, hash, username, phone, name, date)
            in conn.execute('select id, hash, username, phone, name, date from entities')
        ], fp)

The following public methods or properties have also been removed from ``SQLiteSession`` because
they no longer make sense:

* ``list_sessions``. You can ``glob.glob('*.session')`` instead.
* ``clone``.

And the following, which were inherited from ``MemorySession``:

* ``delete``. You can ``os.remove`` the file instead (preferably after ``client.log_out()``).
  ``client.log_out()`` also no longer deletes the session file (it can't as there's no method).
* ``set_dc``.
* ``dc_id``.
* ``server_address``.
* ``port``.
* ``auth_key``.
* ``takeout_id``.
* ``get_update_state``.
* ``set_update_state``.
* ``process_entities``.
* ``get_entity_rows_by_phone``.
* ``get_entity_rows_by_username``.
* ``get_entity_rows_by_name``.
* ``get_entity_rows_by_id``.
* ``get_input_entity``.
* ``cache_file``.
* ``get_file``.

You also can no longer set ``client.session.save_entities = False``. The entities must be saved
for the library to work properly. If you still don't want it, you should subclass the session and
override the methods to do nothing.


Complete overhaul of errors
---------------------------

The following error name have changed to follow a better naming convention (clearer acronyms):

* ``RPCError`` is now ``RpcError``.
* ``InvalidDCError`` is now ``InvalidDcError`` (lowercase ``c``).

The base errors no longer have a ``.message`` field at the class-level. Instead, it is now an
attribute at the instance level (meaning you cannot do ``BadRequestError.message``, it must be
``bad_request_err.message`` where ``isinstance(bad_request_err, BadRequestError)``).

The ``.message`` will gain its value at the time the error is constructed, rather than being
known beforehand.

The parameter order for ``RpcError`` and all its subclasses are now ``(code, message, request)``,
as opposed to ``(message, request, code)``.

Because Telegram errors can be added at any time, the library no longer generate a fixed set of
them. This means you can no longer use ``dir`` to get a full list of them. Instead, the errors
are automatically generated depending on the name you use for the error, with the following rules:

* Numbers are removed from the name. The Telegram error ``FLOOD_WAIT_42`` is transformed into
  ``FLOOD_WAIT_``.
* Underscores are removed from the name. ``FLOOD_WAIT_`` becomes ``FLOODWAIT``.
* Everything is lowercased. ``FLOODWAIT`` turns into ``floodwait``.
* While the name ends with ``error``, this suffix is removed.

The only exception to this rule is ``2FA_CONFIRM_WAIT_0``, which is transformed as
``twofaconfirmwait`` (read as ``TwoFaConfirmWait``).

What all this means is that, if Telegram raises a ``FLOOD_WAIT_42``, you can write the following:

.. code-block:: python

    from telethon.errors import FloodWaitError

    try:
        await client.send_message(chat, message)
    except FloodWaitError as e:
        print(f'Flood! wait for {e.seconds} seconds')

Essentially, old code will keep working, but now you have the freedom to define even yet-to-be
discovered errors. This makes use of `PEP 562 <https://www.python.org/dev/peps/pep-0562/>`__ on
Python 3.7 and above and a more-hacky approach below (which your IDE may not love).

Given the above rules, you could also write ``except errors.FLOOD_WAIT`` if you prefer to match
Telegram's naming conventions. We recommend Camel-Case naming with the "Error" suffix, but that's
up to you.

All errors will include a list of ``.values`` (the extracted number) and ``.value`` (the first
number extracted, or ``None`` if ``values`` is empty). In addition to that, certain errors have
a more-recognizable alias (such as ``FloodWait`` which has ``.seconds`` for its ``.value``).

The ``telethon.errors`` module continues to provide certain predefined ``RpcError`` to match on
the *code* of the error and not its message (for instance, match all errors with code 403 with
``ForbiddenError``). Note that a certain error message can appear with different codes too, this
is decided by Telegram.

The ``telethon.errors`` module continues to provide custom errors used by the library such as
``TypeNotFoundError``.

// TODO keep RPCError around? eh idk how much it's used
// TODO should RpcError subclass ValueError? technically the values used in the request somehow were wrong…
// TODO provide a way to see which errors are known in the docs or at tl.telethon.dev


Changes to the default parse mode
---------------------------------

The default markdown parse mode now conforms to the commonmark specification.

The old markdown parser (which was used as the default ``client.parse_mode``) used to emulate
Telegram Desktop's behaviour. Now `<markdown-it-py https://github.com/executablebooks/markdown-it-py>`__
is used instead, which fixes certain parsing bugs but also means the formatting will be different.

Most notably, ``__`` will now make text bold. If you want the old behaviour, use a single
underscore instead (such as ``_``). You can also use a single asterisk (``*``) for italics.
Because now there's proper parsing, you also gain:

* Headings (``# text``) will now be underlined.
* Certain HTML tags will now also be recognized in markdown (including ``<u>`` for underlining text).
* Line breaks behave properly now. For a single-line break, end your line with ``\\``.
* Inline links should no longer behave in a strange manner.
* Pre-blocks can now have a language. Official clients don't syntax highlight code yet, though.

Furthermore, the parse mode is no longer client-dependant. It is now configured through ``Message``.

// TODO provide a way to get back the old behaviour?


The "iter" variant of the client methods have been removed
----------------------------------------------------------

Instead, you can now use the result of the ``get_*`` variant. For instance, where before you had:

.. code-block:: python

    async for message in client.iter_messages(...):
        pass

You would now do:

    .. code-block:: python

        async for message in client.get_messages(...):
            pass                  # ^^^ now it's get, not iter

You can still use ``await`` on the ``get_`` methods to retrieve the list.

The removed methods are:

* iter_messages
* iter_dialogs
* iter_participants
* iter_admin_log
* iter_profile_photos
* iter_drafts

The only exception to this rule is ``iter_download``.

Additionally, when using ``await``, if the method was called with a limit of 1 (either through
setting just one value to fetch, or setting the limit to one), either ``None`` or a single item
(outside of a ``list``) will be returned. This used to be the case only for ``get_messages``,
but now all methods behave in the same way for consistency.

When using ``async for``, the default limit will be ``None``, meaning all items will be fetched.
When using ``await``, the default limit will be ``1``, meaning the latest item will be fetched.
If you want to use ``await`` but still get a list, use the ``.collect()`` method to collect the
results into a list:

.. code-block:: python

    chat = ...

    # will iterate over all (default limit=None)
    async for message in client.get_messages(chat):
        ...

    # will return either a single Message or None if there is not any (limit=1)
    message = await client.get_messages(chat)

    # will collect all messages into a list (default limit=None). will also take long!
    all_messages = await client.get_messages(chat).collect()


// TODO keep providing the old ``iter_`` versions? it doesn't really hurt, even if the recommended way changed
// TODO does the download really need to be special? get download is kind of weird though


Raw API has been renamed and is now immutable and considered private
--------------------------------------------------------------------

The subpackage holding the raw API methods has been renamed from ``tl`` to ``_tl`` in order to
signal that these are prone to change across minor version bumps (the ``y`` in version ``x.y.z``).

Because in Python "we're all adults", you *can* use this private module if you need to. However,
you *are* also acknowledging that this is a private module prone to change (and indeed, it will
change on layer upgrades across minor version bumps).

The ``Request`` suffix has been removed from the classes inside ``tl.functions``.

The ``tl.types`` is now simply ``_tl``, and the ``tl.functions`` is now ``_tl.fn``.

Both the raw API types and functions are now immutable. This can enable optimizations in the
future, such as greatly reducing the number of intermediate objects created (something worth
doing for deeply-nested objects).

Some examples:

.. code-block:: python

    # Before
    from telethon.tl import types, functions

    await client(functions.messages.SendMessageRequest(...))
    message: types.Message = ...

    # After
    from telethon import _tl
    await client(_tl.fn.messages.SendMessage(...))
    message: _tl.Message

This serves multiple goals:

* It removes redundant parts from the names. The "recommended" way of using the raw API is through
  the subpackage namespace, which already contains a mention to "functions" in it. In addition,
  some requests were awkward, such as ``SendCustomRequestRequest``.
* It makes it easier to search for code that is using the raw API, so that you can quickly
  identify which parts are making use of it.
* The name is shorter, but remains recognizable.

Because *a lot* of these objects are created, they now define ``__slots__``. This means you can
no longer monkey-patch them to add new attributes at runtime. You have to create a subclass if you
want to define new attributes.

This also means that the updates from ``events.Raw`` **no longer have** ``update._entities``.

``tlobject.to_dict()`` has changed and is now generated dynamically based on the ``__slots__`.
This may incur a small performance hit (but you shouldn't really be using ``.to_dict()`` when
you can just use attribute access and ``getattr``). In general, this should handle ill-defined
objects more gracefully (for instance, those where you're using a ``tuple`` and not a ``list``
or using a list somewhere it shouldn't be), and have no other observable effects. As an extra
benefit, this slightly cuts down on the amount of bloat.

In ``tlobject.to_dict()``, the special ``_`` key is now also contains the module (so you can
actually distinguish between equally-named classes). If you want the old behaviour, use
``tlobject.__class__.__name__` instead (and add ``Request`` for functions).

Because the string representation of an object used ``tlobject.to_dict()``, it is now also
affected by these changes.

// TODO this definitely generated files mapping from the original name to this new one...
// TODO what's the alternative to update._entities? and update._client??


Many subpackages and modules are now private
--------------------------------------------

There were a lot of things which were public but should not have been. From now on, you should
only rely on things that are either publicly re-exported or defined. That is, as soon as anything
starts with an underscore (``_``) on its name, you're acknowledging that the functionality may
change even across minor version changes, and thus have your code break.

The following subpackages are now considered private:

* ``client`` is now ``_client``.
* ``crypto`` is now ``_crypto``.
* ``extensions`` is now ``_misc``.
* ``tl`` is now ``_tl``.

The following modules have been moved inside ``_misc``:

* ``entitycache.py``
* ``helpers.py``
* ``hints.py``
* ``password.py``
* ``requestiter.py``
* ``statecache.py``
* ``utils.py``

// TODO review telethon/__init__.py isn't exposing more than it should


Using the client in a context-manager no longer calls start automatically
-------------------------------------------------------------------------

The following code no longer automatically calls ``client.start()``:

.. code-block:: python

    async with TelegramClient(...) as client:
        ...

    # or

    async with client:
        ...


This means the context-manager will only call ``client.connect()`` and ``client.disconnect()``.
The rationale for this change is that it could be strange for this to ask for the login code if
the session ever was invalid. If you want the old behaviour, you now need to be explicit:


.. code-block:: python

    async with TelegramClient(...).start() as client:
        ...  #                    ++++++++


Note that you do not need to ``await`` the call to ``.start()`` if you are going to use the result
in a context-manager (but it's okay if you put the ``await``).


Changes to sending messages and files
-------------------------------------

When sending messages or files, there is no longer a parse mode. Instead, the ``markdown`` or
``html`` parameters can be used instead of the (plaintext) ``message``.

.. code-block:: python

    await client.send_message(chat, 'Default formatting (_markdown_)')
    await client.send_message(chat, html='Force <em>HTML</em> formatting')
    await client.send_message(chat, markdown='Force **Markdown** formatting')

These 3 parameters are exclusive with each other (you can only use one). The goal here is to make
it consistent with the custom ``Message`` class, which also offers ``.markdown`` and ``.html``
properties to obtain the correctly-formatted text, regardless of the default parse mode, and to
get rid of some implicit behaviour. It's also more convenient to set just one parameter than two
(the message and the parse mode separatedly).

Although the goal is to reduce raw API exposure, ``formatting_entities`` stays, because it's the
only feasible way to manually specify them.

When sending files, you can no longer pass a list of attributes. This was a common workaround to
set video size, audio duration, and so on. Now, proper parameters are available. The goal is to
hide raw API as much as possible (which lets the library hide future breaking changes as much as
possible). One can still use raw API if really needed.


Several methods have been removed from the client
-------------------------------------------------

``client.download_file`` has been removed. Instead, ``client.download_media`` should be used.
The now-removed ``client.download_file`` method was a lower level implementation which should
have not been exposed at all.

``client.build_reply_markup`` has been removed. Manually calling this method was purely an
optimization (the buttons won't need to be transformed into a reply markup every time they're
used). This means you can just remove any calls to this method and things will continue to work.


Support for bot-API style file_id has been removed
--------------------------------------------------

They have been half-broken for a while now, so this is just making an existing reality official.
See `issue #1613 <https://github.com/LonamiWebs/Telethon/issues/1613>`__ for details.

An alternative solution to re-use files may be provided in the future. For the time being, you
should either upload the file as needed, or keep a message with the media somewhere you can
later fetch it (by storing the chat and message identifier).

Additionally, the ``custom.File.id`` property is gone (which used to provide access to this
"bot-API style" file identifier.

// TODO could probably provide an in-memory cache for uploads to temporarily reuse old InputFile.
// this should lessen the impact of the removal of this feature


Removal of several utility methods
----------------------------------

The following ``utils`` methods no longer exist or have been made private:

* ``utils.resolve_bot_file_id``. It was half-broken.
* ``utils.pack_bot_file_id``. It was half-broken.
* ``utils.resolve_invite_link``. It has been broken for a while, so this just makes its removal
  official (see `issue #1723 <https://github.com/LonamiWebs/Telethon/issues/1723>`__).
* ``utils.resolve_id``. Marked IDs are no longer used thorough the library. The removal of this
  method also means ``utils.get_peer`` can no longer get a ``Peer`` from just a number, as the
  type is no longer embedded inside the ID.

// TODO provide the new clean utils


Changes to many friendly methods in the client
----------------------------------------------

Some of the parameters used to initialize the ``TelegramClient`` have been renamed to be clearer:

* ``timeout`` is now ``connect_timeout``.
* ``connection_retries`` is now ``connect_retries``.
* ``retry_delay`` is now ``connect_retry_delay``.
* ``raise_last_call_error`` has been removed and is now the default. This means you won't get a
  ``ValueError`` if an API call fails multiple times, but rather the original error.
* ``connection`` to change the connection mode has been removed for the time being.
* ``sequential_updates`` has been removed for the time being.

// TODO document new parameters too

``client.send_code_request`` no longer has ``force_sms`` (it was broken and was never reliable).

``client.send_read_acknowledge`` is now ``client.mark_read``, consistent with the method of
``Message``, being shorter and less awkward to type. The method now only supports a single
message, not a list (the list was a lie, because all messages up to the one with the highest
ID were marked as read, meaning one could not leave unread gaps). ``max_id`` is now removed,
since it has the same meaning as the message to mark as read. The method no longer can clear
mentions without marking the chat as read, but this should not be an issue in practice.

Every ``client.action`` can now be directly ``await``-ed, not just ``'cancel'``.

``client.forward_messages`` now requires a list to be specified. The intention is to make it clear
that the method forwards message\ **s** and to reduce the number of strange allowed values, which
needlessly complicate the code. If you still need to forward a single message, manually construct
a list with ``[message]`` or use ``Message.forward_to``.

``client.delete_messages`` now requires a list to be specified, with the same rationale as forward.

``client.get_me`` no longer has an ``input_peer`` parameter. The goal is to hide raw API as much
as possible. Input peers are mostly an implementation detail the library needs to deal with
Telegram's API.

Before, ``client.iter_participants`` (and ``get_participants``) would expect a type or instance
of the raw Telegram definition as a ``filter``. Now, this ``filter`` expects a string.
The supported values are:

* ``'admin'``
* ``'bot'``
* ``'kicked'``
* ``'banned'``
* ``'contact'``

If you prefer to avoid hardcoding strings, you may use ``telethon.enums.Participant``.

The size selector for ``client.download_profile_photo`` and ``client.download_media`` is now using
an enumeration:

.. code-block:: python

    from telethon import enums

    await client.download_profile_photo(user, thumb=enums.Size.ORIGINAL)

This new selection mode is also smart enough to pick the "next best" size if the specified one
is not available. The parameter is known as ``thumb`` and not ``size`` because documents don't
have a "size", they have thumbnails of different size. For profile photos, the thumbnail size is
also used.

// TODO maintain support for the old way of doing it?
// TODO now that there's a custom filter, filter client-side for small chats?


The custom.Message class and the way it is used has changed
-----------------------------------------------------------

It no longer inherits ``TLObject``, and rather than trying to mimick Telegram's ``Message``
constructor, it now takes two parameters: a ``TelegramClient`` instance and a ``_tl.Message``.
As a benefit, you can now more easily reconstruct instances of this type from a previously-stored
``_tl.Message`` instance.

There are no public attributes. Instead, they are now properties which forward the values into and
from the private ``_message`` field. As a benefit, the documentation will now be easier to follow.
However, you can no longer use ``del`` on these.

The ``_tl.Message.media`` attribute will no longer be ``None`` when using raw API if the media was
``messageMediaEmpty``. As a benefit, you can now actually distinguish between no media and empty
media. The ``Message.media`` property as returned by friendly methods will still be ``None`` on
empty media.

The ``telethon.tl.patched`` hack has been removed.

The message sender no longer is the channel when no sender is provided by Telegram. Telethon used
to patch this value for channels to be the same as the chat, but now it will be faithful to
Telegram's value.


Overhaul of users and chats are no longer raw API types
-------------------------------------------------------

Users and chats are no longer raw API types. The goal is to reduce the amount of raw API exposed
to the user, and to provide less confusing naming. This also means that **the sender and chat of
messages and events is now a different type**. If you were using `isinstance` to check the types,
you will need to update that code. However, if you were accessing things like the ``first_name``
or ``username``, you will be fine.

Raw API is not affected by this change. When using it, the raw :tl:`User`, :tl:`Chat` and
:tl:`Channel` are still returned.

For friendly methods and events, There are now two main entity types, `User` and `Chat`.
`User`\ s are active entities which can send messages and interact with eachother. There is an
account controlling them. `Chat`\ s are passive entities where multiple users can join and
interact with each other. This includes small groups, supergroups, and broadcast channels.

``event.get_sender``, ``event.sender``, ``event.get_chat``, and ``event.chat`` (as well as
the same methods on ``message`` and elsewhere) now return this new type. The ``sender`` and
``chat`` is **now always returned** (where it makes sense, so no sender in channel messages),
even if Telegram did not include information about it in the update. This means you can use
send messages to ``event.chat`` without worrying if Telegram included this information or not,
or even access ``event.chat.id``. This was often a papercut. However, if you need other
information like the title, you might still need to use ``await event.get_chat()``, which is
used to signify an API call might be necessary.

``event.get_input_sender``, ``event.input_sender``, ``message.get_input_sender`` and
``message.input_sender`` (among other variations) have been removed. Instead, a new ``compact``
method has been added to the new `User` and `Chat` types, which can be used to obtain a compact
representation of the sender. The "input" terminology is confusing for end-users, as it's mostly
an implementation detail of friendly methods. Because the return type would've been different
had these methods been kept, one would have had to review code using them regardless.

What this means is that, if you now want a compact way to store a user or chat for later use,
you should use ``compact``:

.. code-block:: python

    compacted_user = message.sender.compact()
    # store compacted_user in a database or elsewhere for later use

Public methods accept this type as input parameters. This means you can send messages to a
compacted user or chat, for example.

``event.is_private``, ``event.is_group`` and ``event.is_channel`` have **been removed** (among
other variations, such as in ``message``). It didn't make much sense to ask "is this event a
group", and there is no such thing as "group messages" currently either. Instead, it's sensible
to ask if the sender of a message is a group, or the chat of an event is a channel. New properties
have been added to both the `User` and `Chat` classes:

* ``.is_user`` will always be `True` for `User` and `False` for `Chat`.
* ``.is_group`` will be `False` for `User` and be `True` for small group chats and supergroups.
* ``.is_broadcast`` will be `False` for `User` and `True` for broadcast channels and broadcast groups.

Because the properties exist both in `User` and `Chat`, you do not need use `isinstance` to check
if a sender is a channel or if a chat is a user.

Some fields of the new `User` type differ from the naming or value type of its raw API counterpart:

* ``user.restriction_reason`` has been renamed to ``restriction_reasons`` (with a trailing **s**)
  and now always returns a list.
* ``user.bot_chat_history`` has been renamed to ``user.bot_info.chat_history_access``.
* ``user.bot_nochats`` has been renamed to ``user.bot_info.private_only``.
* ``user.bot_inline_geo`` has been renamed to ``user.bot_info.inline_geo``.
* ``user.bot_info_version`` has been renamed to ``user.bot_info.version``.
* ``user.bot_inline_placeholder`` has been renamed to ``user.bot_info.inline_placeholder``.

The new ``user.bot_info`` field will be `None` for non-bots. The goal is to unify where this
information is found and reduce clutter in the main ``user`` type.

Some fields of the new `Chat` type differ from the naming or value type of its raw API counterpart:

* ``chat.date`` is currently not available. It's either the chat creation or join date, but due
  to this inconsistency, it's not included to allow for a better solution in the future.
* ``chat.has_link`` is currently not available, to allow for a better alternative in the future.
* ``chat.has_geo`` is currently not available, to allow for a better alternative in the future.
* ``chat.call_active`` is currently not available, until it's decided what to do about calls.
* ``chat.call_not_empty`` is currently not available, until it's decided what to do about calls.
* ``chat.version`` was removed. It's an implementation detail.
* ``chat.min`` was removed. It's an implementation detail.
* ``chat.deactivated`` was removed. It's redundant with ``chat.migrated_to``.
* ``chat.forbidden`` has been added as a replacement for ``isinstance(chat, (ChatForbidden, ChannelForbidden))``.
* ``chat.forbidden_until`` has been added as a replacement for ``until_date`` in forbidden chats.
* ``chat.restriction_reason`` has been renamed to ``restriction_reasons`` (with a trailing **s**)
  and now always returns a list.
* ``chat.migrated_to`` no longer returns a raw type, and instead returns this new `Chat` type.

If you have a need for these, please step in, and explain your use case, so we can work together
to implement a proper design.

Both the new `User` and `Chat` types offer a ``fetch`` method, which can be used to refetch the
instance with fresh information, including the full information about the user (such as the user's
biography or a chat's about description).


Using a flat list to define buttons will now create rows and not columns
------------------------------------------------------------------------

When sending a message with buttons under a bot account, passing a flat list such as the following:

.. code-block:: python

    bot.send_message(chat, message, buttons=[
        Button.inline('top'),
        Button.inline('middle'),
        Button.inline('bottom'),
    ])

Will now send a message with 3 rows of buttons, instead of a message with 3 columns (old behaviour).
If you still want the old behaviour, wrap the list inside another list:

.. code-block:: python

    bot.send_message(chat, message, buttons=[[
        #                                   +
        Button.inline('left'),
        Button.inline('center'),
        Button.inline('right'),
    ]])
    #+


Changes to the string and to_dict representation
------------------------------------------------

The string representation of raw API objects will now have its "printing depth" limited, meaning
very large and nested objects will be easier to read.

If you want to see the full object's representation, you should instead use Python's builtin
``repr`` method.

The ``.stringify`` method remains unchanged.

Here's a comparison table for a convenient overview:

+-------------------+---------------------------------------------+---------------------------------------------+
|                   |               Telethon v1.x                 |                 Telethon v2.x               |
+-------------------+-------------+--------------+----------------+-------------+--------------+----------------+
|                   | ``__str__`` | ``__repr__`` | ``.stringify`` | ``__str__`` | ``__repr__`` | ``.stringify`` |
+-------------------+-------------+--------------+----------------+-------------+--------------+----------------+
|           Useful? |      ✅     |      ❌      |        ✅      |      ✅     |       ✅     |        ✅      |
+-------------------+-------------+--------------+----------------+-------------+--------------+----------------+
|        Multiline? |      ❌     |      ❌      |        ✅      |      ❌     |       ❌     |        ✅      |
+-------------------+-------------+--------------+----------------+-------------+--------------+----------------+
| Shows everything? |      ✅     |      ❌      |        ✅      |      ❌     |       ✅     |        ✅      |
+-------------------+-------------+--------------+----------------+-------------+--------------+----------------+

Both of the string representations may still change in the future without warning, as Telegram
adds, changes or removes fields. It should only be used for debugging. If you need a persistent
string representation, it is your job to decide which fields you care about and their format.

The ``Message`` representation now contains different properties, which should be more useful and
less confusing.


Changes on how to configure a different connection mode
-------------------------------------------------------

The ``connection`` parameter of the ``TelegramClient`` now expects a string, and not a type.
The supported values are:

* ``'full'``
* ``'intermediate'``
* ``'abridged'``
* ``'obfuscated'``
* ``'http'``

The value chosen by the library is left as an implementation detail which may change. However,
you can force a certain mode by explicitly configuring it. If you don't want to hardcode the
string, you can import these values from the new ``telethon.enums`` module:

.. code-block:: python

    client = TelegramClient(..., connection='tcp')

    # or

    from telethon.enums import ConnectionMode
    client = TelegramClient(..., connection=ConnectionMode.TCP)

You may have noticed there's currently no alternative for ``TcpMTProxy``. This mode has been
broken for some time now (see `issue #1319 <https://github.com/LonamiWebs/Telethon/issues/1319>`__)
anyway, so until there's a working solution, the mode is not supported. Pull Requests are welcome!


The to_json method on objects has been removed
----------------------------------------------

This was not very useful, as most of the time, you'll probably be having other data along with the
object's JSON. It simply saved you an import (and not even always, in case you wanted another
encoder). Use ``json.dumps(obj.to_dict())`` instead.


The Conversation API has been removed
-------------------------------------

This API had certain shortcomings, such as lacking persistence, poor interaction with other event
handlers, and overcomplicated usage for anything beyond the simplest case.

It is not difficult to write your own code to deal with a conversation's state. A simple
`Finite State Machine <https://stackoverflow.com/a/62246569/>`__ inside your handlers will do
just fine This approach can also be easily persisted, and you can adjust it to your needs and
your handlers much more easily.

// TODO provide standalone alternative for this?


Certain client properties and methods are now private or no longer exist
------------------------------------------------------------------------

The ``client.loop`` property has been removed. ``asyncio`` has been moving towards implicit loops,
so this is the next step. Async methods can be launched with the much simpler ``asyncio.run`` (as
opposed to the old ``client.loop.run_until_complete``).

The ``client.upload_file`` method has been removed. It's a low-level method users should not need
to use. Its only purpose could have been to implement a cache of sorts, but this is something the
library needs to do, not the users.

The methods to deal with folders have been removed. The goal is to find and offer a better
interface to deal with both folders and archived chats in the future if there is demand for it.
This includes the removal of ``client.edit_folder``, ``Dialog.archive``, ``Dialog.archived``, and
the ``archived`` parameter of ``client.get_dialogs``. The ``folder`` parameter remains as it's
unlikely to change.


Deleting messages now returns a more useful value
-------------------------------------------------

It used to return a list of :tl:`messages.affectedMessages` which I expect very little people were
actually using. Now it returns an ``int`` value indicating the number of messages that did exist
and were deleted.


Changes to the methods to retrieve participants
-----------------------------------------------

The "aggressive" hack in ``get_participants`` (and ``iter_participants``) is now gone.
It was not reliable, and was a cause of flood wait errors.

The ``search`` parameter is no longer ignored when ``filter`` is specified.


The total value when getting participants has changed
-----------------------------------------------------

Before, it used to always be the total amount of people inside the chat. Now the filter is also
considered. If you were running ``client.get_participants`` with a ``filter`` other than the
default and accessing the ``list.total``, you will now get a different result. You will need to
perform a separate request with no filter to fetch the total without filter (this is what the
library used to do).


Changes to editing messages
---------------------------

Before, calling ``message.edit()`` would completely ignore your attempt to edit a message if the
message had a forward header or was not outgoing. This is no longer the case. It is now the user's
responsibility to check for this.

However, most likely, you were already doing the right thing (or else you would've experienced a
"why is this not being edited", which you would most likely consider a bug rather than a feature).

When using ``client.edit_message``, you now must always specify the chat and the message (or
message identifier). This should be less "magic". As an example, if you were doing this before:

.. code-block:: python

    await client.edit_message(message, 'new text')

You now have to do the following:

.. code-block:: python

    await client.edit_message(message.input_chat, message.id, 'new text')

    # or

    await message.edit('new text')


Signing in no longer sends the code
-----------------------------------

``client.sign_in()`` used to run ``client.send_code_request()`` if you only provided the phone and
not the code. It no longer does this. If you need that convenience, use ``client.start()`` instead.


The client.disconnected property has been removed
-------------------------------------------------

``client.run_until_disconnected()`` should be used instead.


The TelegramClient is no longer made out of mixins
--------------------------------------------------

If you were relying on any of the individual mixins that made up the client, such as
``UserMethods`` inside the ``telethon.client`` subpackage, those are now gone.
There is a single ``TelegramClient`` class now, containing everything you need.


The takeout context-manager has changed
---------------------------------------

It no longer has a finalize. All the requests made by the client in the same task will be wrapped,
not only those made through the proxy client returned by the context-manager.

This cleans up the (rather hacky) implementation, making use of Python's ``contextvar``. If you
still need the takeout session to persist, you should manually use the ``begin_takeout`` and
``end_takeout`` method.

If you want to ignore the currently-active takeout session in a task, toggle the following context
variable:

.. code-block:: python

    telethon.ignore_takeout.set(True)


CdnDecrypter has been removed
-----------------------------

It was not really working and was more intended to be an implementation detail than anything else.


URL buttons no longer open the web-browser
------------------------------------------

Now the URL is returned. You can still use ``webbrowser.open`` to get the old behaviour.


---

todo update send_message and send_file docs (well review all functions)

album overhaul. use a list of Message instead.

is_connected is now a property (consistent with the rest of ``is_`` properties)

send_code_request now returns a custom type (reducing raw api).
sign_in no longer has phone or phone_hash (these are impl details, and now it's less error prone). also mandatory code=. also no longer is a no-op if already logged in. different error for sign up required.
send code / sign in now only expect a single phone. resend code with new phone is send code, not resend.
sign_up code is also now a kwarg. and no longer noop if already loggedin.
start also mandates phone= or password= as kwarg.
qrlogin expires has been replaced with timeout and expired for parity with tos and auth. the goal is to hide the error-prone system clock and instead use asyncio's clock. recreate was removed (just call qr_login again; parity with get_tos). class renamed to QrLogin. now must be used in a contextmgr to prevent misuse.
"entity" parameters have been renamed to "dialog" (user or chat expected) or "chat" (only chats expected), "profile" (if that makes sense). the goal is to move away from the entity terminology. this is intended to be a documentation change, but because the parameters were renamed, it's breaking. the expected usage of positional arguments is mostly unaffected. this includes the EntityLike hint.
download_media param renamed message to media. iter_download file to media too
less types are supported to get entity (exact names, private links are undocumented but may work). get_entity is get_profile. get_input_entity is gone. get_peer_id is gone (if the isntance needs to be fetched anyway just use get_profile).
