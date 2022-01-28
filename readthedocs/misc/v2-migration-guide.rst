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


Raw API has been renamed and is now considered private
------------------------------------------------------

The subpackage holding the raw API methods has been renamed from ``tl`` to ``_tl`` in order to
signal that these are prone to change across minor version bumps (the ``y`` in version ``x.y.z``).

Because in Python "we're all adults", you *can* use this private module if you need to. However,
you *are* also acknowledging that this is a private module prone to change (and indeed, it will
change on layer upgrades across minor version bumps).

The ``Request`` suffix has been removed from the classes inside ``tl.functions``.

The ``tl.types`` is now simply ``_tl``, and the ``tl.functions`` is now ``_tl.fn``.

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
* ``requestiter.py`
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


Changes on how to configure filters for certain client methods
--------------------------------------------------------------

Before, ``client.iter_participants`` (and ``get_participants``) would expect a type or instance
of the raw Telegram definition as a ``filter``. Now, this ``filter`` expects a string.
The supported values are:

* ``'admin'``
* ``'bot'``
* ``'kicked'``
* ``'banned'``
* ``'contact'``

If you prefer to avoid hardcoding strings, you may use ``telethon.enums.Participant``.

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

In order to avoid breaking more code than strictly necessary, ``.raw_text`` will remain a synonym
of ``.message``, and ``.text`` will still be the text formatted through the ``client.parse_mode``.
However, you're encouraged to change uses of ``.raw_text`` with ``.message``, and ``.text`` with
either ``.md_text`` or ``.html_text`` as needed. This is because both ``.text`` and ``.raw_text``
may disappear in future versions, and their behaviour is not immediately obvious.

// TODO actually provide the things mentioned here


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
        Button.inline('top'),
        Button.inline('middle'),
        Button.inline('bottom'),
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

you can no longer pass an attributes list because the constructor is now nice.
use raw api if you really need it.
goal is to hide raw api from high level api. sorry.

no parsemode. use the correct parameter. it's more convenient than setting two.

formatting_entities stays because otherwise it's the only feasible way to manually specify it.

todo update send_message and send_file docs (well review all functions)

album overhaul. use a list of Message instead.

size selector for download_profile_photo and download_media is now different

still thumb because otherwise documents are weird.

keep support for explicit size instance?

renamed send_read_acknowledge. add send_read_acknowledge as alias for mark_read?

force sms removed as it was broken anyway and not very reliable

you can now await client.action for a one-off any action not just cancel

fwd msg and delete msg now mandate a list rather than a single int or msg
(since there's msg.delete and msg.forward_to this should be no issue).
they are meant to work on lists.

also mark read only supports single now. a list would just be max anyway.
removed max id since it's not really of much use.

client loop has been removed. embrace implicit loop as asyncio does now

renamed some client params, and made other privates
    timeout -> connect_timeout
    connection_retries -> connect_retries
    retry_delay -> connect_retry_delay

sequential_updates is gone
connection type is gone

raise_last_call_error is now the default rather than ValueError

self-produced updates like getmessage now also trigger a handler

input_peer removed from get_me; input peers should remain mostly an impl detail

raw api types and fns are now immutable. this can enable optimizations in the future.

upload_file has been removed from the public methods. it's a low-level method users should not need to use.

events have changed. rather than differentiating between "event builder" and "event instance", instead there is only the instance, and you register the class.
where you had
@client.on(events.NewMessage(chats=...))
it's now
@client.on(events.NewMessage, chats=...)
this also means filters are unified, although not all have an effect on all events. from_users renamed to senders. messageread inbox is gone in favor of outgoing/incoming.
events.register, unregister, is_handler and list are gone. now you can typehint instead.
def handler(event: events.NewMessage)
client.on, add, and remove have changed parameters/retval