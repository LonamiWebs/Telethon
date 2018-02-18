.. _changelog:


===========================
Changelog (Version History)
===========================


This page lists all the available versions of the library,
in chronological order. You should read this when upgrading
the library to know where your code can break, and where
it can take advantage of new goodies!

.. contents:: List of All Versions


New small convenience functions (v0.17.3)
=========================================

*Published at 2018/02/18*

More bug fixes and a few others addition to make events easier to use.

Additions
~~~~~~~~~

- Use ``hachoir`` to extract video and audio metadata before upload.
- New ``.add_event_handler``, ``.add_update_handler`` now deprecated.

Bug fixes
~~~~~~~~~

- ``bot_token`` wouldn't work on ``.start()``, and changes to ``password``
  (now it will ask you for it if you don't provide it, as docstring hinted).
- ``.edit_message()`` was ignoring the formatting (e.g. markdown).
- Added missing case to the ``NewMessage`` event for normal groups.
- Accessing the ``.text`` of the ``NewMessage`` event was failing due
  to a bug with the markdown unparser.

Internal changes
~~~~~~~~~~~~~~~~

- ``libssl`` is no longer an optional dependency. Use ``cryptg`` instead,
  which you can find on https://github.com/Lonami/cryptg.



New small convenience functions (v0.17.2)
=========================================

*Published at 2018/02/15*

Primarily bug fixing and a few welcomed additions.

Additions
~~~~~~~~~

- New convenience ``.edit_message()`` method on the ``TelegramClient``.
- New ``.edit()`` and ``.delete()`` shorthands on the ``NewMessage`` event.
- Default to markdown parsing when sending and editing messages.
- Support for inline mentions when sending and editing messages. They work
  like inline urls (e.g. ``[text](@username)``) and also support the Bot-API
  style (see `here <https://core.telegram.org/bots/api#formatting-options>`__).

Bug fixes
~~~~~~~~~

- Periodically send ``GetStateRequest`` automatically to keep the server
  sending updates even if you're not invoking any request yourself.
- HTML parsing was failing due to not handling surrogates properly.
- ``.sign_up`` was not accepting ``int`` codes.
- Whitelisting more than one chat on ``events`` wasn't working.
- Video files are sent as a video by default unless ``force_document``.

Internal changes
~~~~~~~~~~~~~~~~

- More ``logging`` calls to help spot some bugs in the future.
- Some more logic to retrieve input entities on events.
- Clarified a few parts of the documentation.


Updates as Events (v0.17.1)
===========================

*Published at 2018/02/09*

Of course there was more work to be done regarding updates, and it's here!
The library comes with a new ``events`` module (which you will often import
as ``from telethon import TelegramClient, events``). This are pretty much
all the additions that come with this version change, but they are a nice
addition. Refer to :ref:`working-with-updates` to get started with events.


Trust the Server with Updates (v0.17)
=====================================

*Published at 2018/02/03*

The library trusts the server with updates again. The library will *not*
check for duplicates anymore, and when the server kicks us, it will run
``GetStateRequest`` so the server starts sending updates again (something
it wouldn't do unless you invoked something, it seems). But this update
also brings a few more changes!

Additions
~~~~~~~~~

- ``TLObject``'s override ``__eq__`` and ``__ne__``, so you can compare them.
- Added some missing cases on ``.get_input_entity()`` and peer functions.
- ``obj.to_dict()`` now has a ``'_'`` key with the type used.
- ``.start()`` can also sign up now.
- More parameters for ``.get_message_history()``.
- Updated list of RPC errors.
- HTML parsing thanks to **@tulir**! It can be used similar to markdown:
  ``client.send_message(..., parse_mode='html')``.


Enhancements
~~~~~~~~~~~~

- ``client.send_file()`` now accepts ``Message``'s and
  ``MessageMedia``'s as the ``file`` parameter.
- Some documentation updates and fixed to clarify certain things.
- New exact match feature on https://lonamiwebs.github.io/Telethon.
- Return as early as possible from ``.get_input_entity()`` and similar,
  to avoid penalizing you for doing this right.

Bug fixes
~~~~~~~~~

- ``.download_media()`` wouldn't accept a ``Document`` as parameter.
- The SQLite is now closed properly on disconnection.
- IPv6 addresses shouldn't use square braces.
- Fix regarding ``.log_out()``.
- The time offset wasn't being used (so having wrong system time would
  cause the library not to work at all).


New ``.resolve()`` method (v0.16.2)
===================================

*Published at 2018/01/19*

The ``TLObject``'s (instances returned by the API and ``Request``'s) have
now acquired a new ``.resolve()`` method. While this should be used by the
library alone (when invoking a request), it means that you can now use
``Peer`` types or even usernames where a ``InputPeer`` is required. The
object now has access to the ``client``, so that it can fetch the right
type if needed, or access the session database. Furthermore, you can
reuse requests that need "autocast" (e.g. you put ``User`` but ``InputPeer``
was needed), since ``.resolve()`` is called when invoking. Before, it was
only done on object construction.

Additions
~~~~~~~~~

- Album support. Just pass a list, tuple or any iterable to ``.send_file()``.


Enhancements
~~~~~~~~~~~~

- ``.start()`` asks for your phone only if required.
- Better file cache. All files under 10MB, once uploaded, should never be
  needed to be re-uploaded again, as the sent media is cached to the session.


Bug fixes
~~~~~~~~~

- ``setup.py`` now calls ``gen_tl`` when installing the library if needed.


Internal changes
~~~~~~~~~~~~~~~~

- The mentioned ``.resolve()`` to perform "autocast", more powerful.
- Upload and download methods are no longer part of ``TelegramBareClient``.
- Reuse ``.on_response()``, ``.__str__`` and ``.stringify()``.
  Only override ``.on_response()`` if necessary (small amount of cases).
- Reduced "autocast" overhead as much as possible.
  You shouldn't be penalized if you've provided the right type.


MtProto 2.0 (v0.16.1)
=====================

*Published at 2018/01/11*

+-----------------------+
| Scheme layer used: 74 |
+-----------------------+

The library is now using MtProto 2.0! This shouldn't really affect you
as an end user, but at least it means the library will be ready by the
time MtProto 1.0 is deprecated.

Additions
~~~~~~~~~

- New ``.start()`` method, to make the library avoid boilerplate code.
- ``.send_file`` accepts a new optional ``thumbnail`` parameter, and
  returns the ``Message`` with the sent file.


Bug fixes
~~~~~~~~~

- The library uses again only a single connection. Less updates are
  be dropped now, and the performance is even better than using temporary
  connections.
- ``without rowid`` will only be used on the ``*.session`` if supported.
- Phone code hash is associated with phone, so you can change your mind
  when calling ``.sign_in()``.


Internal changes
~~~~~~~~~~~~~~~~

- File cache now relies on the hash of the file uploaded instead its path,
  and is now persistent in the ``*.session`` file. Report any bugs on this!
- Clearer error when invoking without being connected.
- Markdown parser doesn't work on bytes anymore (which makes it cleaner).


Sessions as sqlite databases (v0.16)
====================================

*Published at 2017/12/28*

In the beginning, session files used to be pickle. This proved to be bad
as soon as one wanted to add more fields. For this reason, they were
migrated to use JSON instead. But this proved to be bad as soon as one
wanted to save things like entities (usernames, their ID and hash), so
now it properly uses
`sqlite3 <https://docs.python.org/3/library/sqlite3.html>`__,
which has been well tested, to save the session files! Calling
``.get_input_entity`` using a ``username`` no longer will need to fetch
it first, so it's really 0 calls again. Calling ``.get_entity`` will
always fetch the most up to date version.

Furthermore, nearly everything has been documented, thus preparing the
library for `Read the Docs <https://readthedocs.org/>`__ (although there
are a few things missing I'd like to polish first), and the
`logging <https://docs.python.org/3/library/logging.html>`__ are now
better placed.

Breaking changes
~~~~~~~~~~~~~~~~

-  ``.get_dialogs()`` now returns a **single list** instead a tuple
   consisting of a **custom class** that should make everything easier
   to work with.
-  ``.get_message_history()`` also returns a **single list** instead a
   tuple, with the ``Message`` instances modified to make them more
   convenient.

Both lists have a ``.total`` attribute so you can still know how many
dialogs/messages are in total.

Additions
~~~~~~~~~

-  The mentioned use of ``sqlite3`` for the session file.
-  ``.get_entity()`` now supports lists too, and it will make as little
   API calls as possible if you feed it ``InputPeer`` types. Usernames
   will always be resolved, since they may have changed.
-  ``.set_proxy()`` method, to avoid having to create a new
   ``TelegramClient``.
-  More ``date`` types supported to represent a date parameter.

Bug fixes
~~~~~~~~~

-  Empty strings weren't working when they were a flag parameter (e.g.,
   setting no last name).
-  Fix invalid assertion regarding flag parameters as well.
-  Avoid joining the background thread on disconnect, as it would be
   ``None`` due to a race condition.
-  Correctly handle ``None`` dates when downloading media.
-  ``.download_profile_photo`` was failing for some channels.
-  ``.download_media`` wasn't handling ``Photo``.

Internal changes
~~~~~~~~~~~~~~~~

-  ``date`` was being serialized as local date, but that was wrong.
-  ``date`` was being represented as a ``float`` instead of an ``int``.
-  ``.tl`` parser wasn't stripping inline comments.
-  Removed some redundant checks on ``update_state.py``.
-  Use a `synchronized
   queue <https://docs.python.org/3/library/queue.html>`__ instead a
   hand crafted version.
-  Use signed integers consistently (e.g. ``salt``).
-  Always read the corresponding ``TLObject`` from API responses, except
   for some special cases still.
-  A few more ``except`` low level to correctly wrap errors.
-  More accurate exception types.
-  ``invokeWithLayer(initConnection(X))`` now wraps every first request
   after ``.connect()``.

As always, report if you have issues with some of the changes!

IPv6 support (v0.15.5)
======================

*Published at 2017/11/16*

+-----------------------+
| Scheme layer used: 73 |
+-----------------------+

It's here, it has come! The library now **supports IPv6**! Just pass
``use_ipv6=True`` when creating a ``TelegramClient``. Note that I could
*not* test this feature because my machine doesn't have IPv6 setup. If
you know IPv6 works in your machine but the library doesn't, please
refer to `#425 <https://github.com/LonamiWebs/Telethon/issues/425>`_.

Additions
~~~~~~~~~

-  IPv6 support.
-  New method to extract the text surrounded by ``MessageEntity``\ 's,
   in the ``extensions.markdown`` module.

Enhancements
~~~~~~~~~~~~

-  Markdown parsing is Done Right.
-  Reconnection on failed invoke. Should avoid "number of retries
   reached 0" (#270).
-  Some missing autocast to ``Input*`` types.
-  The library uses the ``NullHandler`` for ``logging`` as it should
   have always done.
-  ``TcpClient.is_connected()`` is now more reliable.

.. bug-fixes-1:

Bug fixes
~~~~~~~~~

-  Getting an entity using their phone wasn't actually working.
-  Full entities aren't saved unless they have an ``access_hash``, to
   avoid some ``None`` errors.
-  ``.get_message_history`` was failing when retrieving items that had
   messages forwarded from a channel.

General enhancements (v0.15.4)
==============================

*Published at 2017/11/04*

+-----------------------+
| Scheme layer used: 72 |
+-----------------------+

This update brings a few general enhancements that are enough to deserve
a new release, with a new feature: beta **markdown-like parsing** for
``.send_message()``!

.. additions-1:

Additions
~~~~~~~~~

-  ``.send_message()`` supports ``parse_mode='md'`` for **Markdown**! It
   works in a similar fashion to the official clients (defaults to
   double underscore/asterisk, like ``**this**``). Please report any
   issues with emojies or enhancements for the parser!
-  New ``.idle()`` method so your main thread can do useful job (listen
   for updates).
-  Add missing ``.to_dict()``, ``__str__`` and ``.stringify()`` for
   ``TLMessage`` and ``MessageContainer``.

.. bug-fixes-2:

Bug fixes
~~~~~~~~~

-  The list of known peers could end "corrupted" and have users with
   ``access_hash=None``, resulting in ``struct`` error for it not being
   an integer. You shouldn't encounter this issue anymore.
-  The warning for "added update handler but no workers set" wasn't
   actually working.
-  ``.get_input_peer`` was ignoring a case for ``InputPeerSelf``.
-  There used to be an exception when logging exceptions (whoops) on
   update handlers.
-  "Downloading contacts" would produce strange output if they had
   semicolons (``;``) in their name.
-  Fix some cyclic imports and installing dependencies from the ``git``
   repository.
-  Code generation was using f-strings, which are only supported on
   Python ≥3.6.

Internal changes
~~~~~~~~~~~~~~~~

-  The ``auth_key`` generation has been moved from ``.connect()`` to
   ``.invoke()``. There were some issues were ``.connect()`` failed and
   the ``auth_key`` was ``None`` so this will ensure to have a valid
   ``auth_key`` when needed, even if ``BrokenAuthKeyError`` is raised.
-  Support for higher limits on ``.get_history()`` and
   ``.get_dialogs()``.
-  Much faster integer factorization when generating the required
   ``auth_key``. Thanks @delivrance for making me notice this, and for
   the pull request.

Bug fixes with updates (v0.15.3)
================================

*Published at 2017/10/20*

Hopefully a very ungrateful bug has been removed. When you used to
invoke some request through update handlers, it could potentially enter
an infinite loop. This has been mitigated and it's now safe to invoke
things again! A lot of updates were being dropped (all those gzipped),
and this has been fixed too.

More bug fixes include a `correct
parsing <https://github.com/LonamiWebs/Telethon/commit/ee01724cdb7027c1e38625d31446ba1ea7bade92>`__
of certain TLObjects thanks to @stek29, and
`some <https://github.com/LonamiWebs/Telethon/commit/ed77ba6f8ff115ac624f02f691c9991e5b37be60>`__
`wrong
calls <https://github.com/LonamiWebs/Telethon/commit/16cf94c9add5e94d70c4eee2ac142d8e76af48b9>`__
that would cause the library to crash thanks to @andr-04, and the
``ReadThread`` not re-starting if you were already authorized.

Internally, the ``.to_bytes()`` function has been replaced with
``__bytes__`` so now you can do ``bytes(tlobject)``.

Bug fixes and new small features (v0.15.2)
==========================================

*Published at 2017/10/14*

This release primarly focuses on a few bug fixes and enhancements.
Although more stuff may have broken along the way.

Enhancements
~~~~~~~~~~~~

-  You will be warned if you call ``.add_update_handler`` with no
   ``update_workers``.
-  New customizable threshold value on the session to determine when to
   automatically sleep on flood waits. See
   ``client.session.flood_sleep_threshold``.
-  New ``.get_drafts()`` method with a custom ``Draft`` class by @JosXa.
-  Join all threads when calling ``.disconnect()``, to assert no
   dangling thread is left alive.
-  Larger chunk when downloading files should result in faster
   downloads.
-  You can use a callable key for the ``EntityDatabase``, so it can be
   any filter you need.

.. bug-fixes-3:

Bug fixes
~~~~~~~~~

-  ``.get_input_entity`` was failing for IDs and other cases, also
   making more requests than it should.
-  Use ``basename`` instead ``abspath`` when sending a file. You can now
   also override the attributes.
-  ``EntityDatabase.__delitem__`` wasn't working.
-  ``.send_message()`` was failing with channels.
-  ``.get_dialogs(limit=None)`` should now return all the dialogs
   correctly.
-  Temporary fix for abusive duplicated updates.

.. enhancements-1:

.. internal-changes-1:

Internal changes
~~~~~~~~~~~~~~~~

-  MsgsAck is now sent in a container rather than its own request.
-  ``.get_input_photo`` is now used in the generated code.
-  ``.process_entities`` was being called from more places than only
   ``__call__``.
-  ``MtProtoSender`` now relies more on the generated code to read
   responses.

Custom Entity Database (v0.15.1)
================================

*Published at 2017/10/05*

The main feature of this release is that Telethon now has a custom
database for all the entities you encounter, instead depending on
``@lru_cache`` on the ``.get_entity()`` method.

The ``EntityDatabase`` will, by default, **cache** all the users, chats
and channels you find in memory for as long as the program is running.
The session will, by default, save all key-value pairs of the entity
identifiers and their hashes (since Telegram may send an ID that it
thinks you already know about, we need to save this information).

You can **prevent** the ``EntityDatabase`` from saving users by setting
``client.session.entities.enabled = False``, and prevent the ``Session``
from saving input entities at all by setting
``client.session.save_entities = False``. You can also clear the cache
for a certain user through
``client.session.entities.clear_cache(entity=None)``, which will clear
all if no entity is given.


Additions
~~~~~~~~~

- New method to ``.delete_messages()``.
- New ``ChannelPrivateError`` class.

Enhancements
~~~~~~~~~~~~

- ``.sign_in`` accepts phones as integers.
- Changing the IP to which you connect to is as simple as
  ``client.session.server_address = 'ip'``, since now the
  server address is always queried from the session.

Bug fixes
~~~~~~~~~

- ``.get_dialogs()`` doesn't fail on Windows anymore, and returns the
  right amount of dialogs.
- ``GeneralProxyError`` should be passed to the main thread
  again, so that you can handle it.

Updates Overhaul Update (v0.15)
===============================

*Published at 2017/10/01*

After hundreds of lines changed on a major refactor, *it's finally
here*. It's the **Updates Overhaul Update**; let's get right into it!

Breaking changes
~~~~~~~~~~~~~~~~

-  ``.create_new_connection()`` is gone for good. No need to deal with
   this manually since new connections are now handled on demand by the
   library itself.

Enhancements
~~~~~~~~~~~~

-  You can **invoke** requests from **update handlers**. And **any other
   thread**. A new temporary will be made, so that you can be sending
   even several requests at the same time!
-  **Several worker threads** for your updates! By default, ``None``
   will spawn. I recommend you to work with ``update_workers=4`` to get
   started, these will be polling constantly for updates.
-  You can also change the number of workers at any given time.
-  The library can now run **in a single thread** again, if you don't
   need to spawn any at all. Simply set ``spawn_read_thread=False`` when
   creating the ``TelegramClient``!
-  You can specify ``limit=None`` on ``.get_dialogs()`` to get **all**
   of them[1].
-  **Updates are expanded**, so you don't need to check if the update
   has ``.updates`` or an inner ``.update`` anymore.
-  All ``InputPeer`` entities are **saved in the session** file, but you
   can disable this by setting ``save_entities=False``.
-  New ``.get_input_entity`` method, which makes use of the above
   feature. You **should use this** when a request needs a
   ``InputPeer``, rather than the whole entity (although both work).
-  Assert that either all or None dependent-flag parameters are set
   before sending the request.
-  Phone numbers can have dashes, spaces, or parenthesis. They'll be
   removed before making the request.
-  You can override the phone and its hash on ``.sign_in()``, if you're
   creating a new ``TelegramClient`` on two different places.

Bug fixes
~~~~~~~~~

-  ``.log_out()`` was consuming all retries. It should work just fine
   now.
-  The session would fail to load if the ``auth_key`` had been removed
   manually.
-  ``Updates.check_error`` was popping wrong side, although it's been
   completely removed.
-  ``ServerError``\ 's will be **ignored**, and the request will
   immediately be retried.
-  Cross-thread safety when saving the session file.
-  Some things changed on a matter of when to reconnect, so please
   report any bugs!

.. internal-changes-2:

Internal changes
~~~~~~~~~~~~~~~~

-  ``TelegramClient`` is now only an abstraction over the
   ``TelegramBareClient``, which can only do basic things, such as
   invoking requests, working with files, etc. If you don't need any of
   the abstractions the ``TelegramClient``, you can now use the
   ``TelegramBareClient`` in a much more comfortable way.
-  ``MtProtoSender`` is not thread-safe, but it doesn't need to be since
   a new connection will be spawned when needed.
-  New connections used to be cached and then reused. Now only their
   sessions are saved, as temporary connections are spawned only when
   needed.
-  Added more RPC errors to the list.

**[1]:** Broken due to a condition which should had been the opposite
(sigh), fixed 4 commits ahead on
https://github.com/LonamiWebs/Telethon/commit/62ea77cbeac7c42bfac85aa8766a1b5b35e3a76c.

--------------

**That's pretty much it**, although there's more work to be done to make
the overall experience of working with updates *even better*. Stay
tuned!

Serialization bug fixes (v0.14.2)
=================================

*Published at 2017/09/29*

Bug fixes
~~~~~~~~~

- **Important**, related to the serialization. Every object or request
  that had to serialize a ``True/False`` type was always being serialized
  as ``false``!
- Another bug that didn't allow you to leave as ``None`` flag parameters
  that needed a list has been fixed.

Internal changes
~~~~~~~~~~~~~~~~

- Other internal changes include a somewhat more readable ``.to_bytes()``
  function and pre-computing the flag instead using bit shifting. The
  ``TLObject.constructor_id`` has been renamed to ``TLObject.CONSTRUCTOR_ID``,
  and ``.subclass_of_id`` is also uppercase now.

Farewell, BinaryWriter (v0.14.1)
================================

*Published at 2017/09/28*

Version ``v0.14`` had started working on the new ``.to_bytes()`` method
to dump the ``BinaryWriter`` and its usage on the ``.on_send()`` when
serializing TLObjects, and this release finally removes it. The speed up
when serializing things to bytes should now be over twice as fast
wherever it's needed.

Bug fixes
~~~~~~~~~

- This version is again compatible with Python 3.x versions **below 3.5**
  (there was a method call that was Python 3.5 and above).

Internal changes
~~~~~~~~~~~~~~~~

- Using proper classes (including the generated code) for generating
  authorization keys and to write out ``TLMessage``\ 's.


Several requests at once and upload compression (v0.14)
=======================================================

*Published at 2017/09/27*

New major release, since I've decided that these two features are big
enough:

Additions
~~~~~~~~~

- Requests larger than 512 bytes will be **compressed through
  gzip**, and if the result is smaller, this will be uploaded instead.
- You can now send **multiple requests at once**, they're simply
  ``*var_args`` on the ``.invoke()``. Note that the server doesn't
  guarantee the order in which they'll be executed!

Internally, another important change. The ``.on_send`` function on the
``TLObjects`` is **gone**, and now there's a new ``.to_bytes()``. From
my tests, this has always been over twice as fast serializing objects,
although more replacements need to be done, so please report any issues.

Enhancements
~~~~~~~~~~~~
- Implemented ``.get_input_media`` helper methods. Now you can even use
  another message as input media!


Bug fixes
~~~~~~~~~

- Downloading media from CDNs wasn't working (wrong
  access to a parameter).
- Correct type hinting.
- Added a tiny sleep when trying to perform automatic reconnection.
- Error reporting is done in the background, and has a shorter timeout.
- ``setup.py`` used to fail with wrongly generated code.

Quick fix-up (v0.13.6)
======================

*Published at 2017/09/23*

Before getting any further, here's a quick fix-up with things that
should have been on ``v0.13.5`` but were missed. Specifically, the
**timeout when receiving** a request will now work properly.

Some other additions are a tiny fix when **handling updates**, which was
ignoring some of them, nicer ``__str__`` and ``.stringify()`` methods
for the ``TLObject``\ 's, and not stopping the ``ReadThread`` if you try
invoking something there (now it simply returns ``None``).

Attempts at more stability (v0.13.5)
====================================

*Published at 2017/09/23*

Yet another update to fix some bugs and increase the stability of the
library, or, at least, that was the attempt!

This release should really **improve the experience with the background
thread** that the library starts to read things from the network as soon
as it can, but I can't spot every use case, so please report any bug
(and as always, minimal reproducible use cases will help a lot).

.. bug-fixes-4:

Bug fixes
~~~~~~~~~

-  ``setup.py`` was failing on Python < 3.5 due to some imports.
-  Duplicated updates should now be ignored.
-  ``.send_message`` would crash in some cases, due to having a typo
   using the wrong object.
-  ``"socket is None"`` when calling ``.connect()`` should not happen
   anymore.
-  ``BrokenPipeError`` was still being raised due to an incorrect order
   on the ``try/except`` block.

.. enhancements-2:

Enhancements
~~~~~~~~~~~~

-  **Type hinting** for all the generated ``Request``\ 's and
   ``TLObjects``! IDEs like PyCharm will benefit from this.
-  ``ProxyConnectionError`` should properly be passed to the main thread
   for you to handle.
-  The background thread will only be started after you're authorized on
   Telegram (i.e. logged in), and several other attempts at polishing
   the experience with this thread.
-  The ``Connection`` instance is only created once now, and reused
   later.
-  Calling ``.connect()`` should have a better behavior now (like
   actually *trying* to connect even if we seemingly were connected
   already).
-  ``.reconnect()`` behavior has been changed to also be more consistent
   by making the assumption that we'll only reconnect if the server has
   disconnected us, and is now private.

.. other-changes-1:

Internal changes
~~~~~~~~~~~~~~~~

-  ``TLObject.__repr__`` doesn't show the original TL definition
   anymore, it was a lot of clutter. If you have any complaints open an
   issue and we can discuss it.
-  Internally, the ``'+'`` from the phone number is now stripped, since
   it shouldn't be included.
-  Spotted a new place where ``BrokenAuthKeyError`` would be raised, and
   it now is raised there.

More bug fixes and enhancements (v0.13.4)
=========================================

*Published at 2017/09/18*

.. new-stuff-1:

Additions
~~~~~~~~~

-  ``TelegramClient`` now exposes a ``.is_connected()`` method.
-  Initial authorization on a new data center will retry up to 5 times
   by default.
-  Errors that couldn't be handled on the background thread will be
   raised on the next call to ``.invoke()`` or ``updates.poll()``.

.. bugs-fixed-1:

Bug fixes
~~~~~~~~~~

-  Now you should be able to sign in even if you have
   ``process_updates=True`` and no previous session.
-  Some errors and methods are documented a bit clearer.
-  ``.send_message()`` could randomly fail, as the returned type was not
   expected.
-  ``TimeoutError`` is now ignored, since the request will be retried up
   to 5 times by default.
-  "-404" errors (``BrokenAuthKeyError``\ 's) are now detected when
   first connecting to a new data center.
-  ``BufferError`` is handled more gracefully, in the same way as
   ``InvalidCheckSumError``\ 's.
-  Attempt at fixing some "NoneType has no attribute…" errors (with the
   ``.sender``).

Internal changes
~~~~~~~~~~~~~~~~

-  Calling ``GetConfigRequest`` is now made less often.
-  The ``initial_query`` parameter from ``.connect()`` is gone, as it's
   not needed anymore.
-  Renamed ``all_tlobjects.layer`` to ``all_tlobjects.LAYER`` (since
   it's a constant).
-  The message from ``BufferError`` is now more useful.

Bug fixes and enhancements (v0.13.3)
====================================

*Published at 2017/09/14*

.. bugs-fixed-2:

Bug fixes
---------

-  **Reconnection** used to fail because it tried invoking things from
   the ``ReadThread``.
-  Inferring **random ids** for ``ForwardMessagesRequest`` wasn't
   working.
-  Downloading media from **CDNs** failed due to having forgotten to
   remove a single line.
-  ``TcpClient.close()`` now has a **``threading.Lock``**, so
   ``NoneType has no close()`` should not happen.
-  New **workaround** for ``msg seqno too low/high``. Also, both
   ``Session.id/seq`` are not saved anymore.

.. enhancements-3:

Enhancements
------------

-  **Request will be retried** up to 5 times by default rather than
   failing on the first attempt.
-  ``InvalidChecksumError``\ 's are now **ignored** by the library.
-  ``TelegramClient.get_entity()`` is now **public**, and uses the
   ``@lru_cache()`` decorator.
-  New method to **``.send_voice_note()``**\ 's.
-  Methods to send message and media now support a **``reply_to``
   parameter**.
-  ``.send_message()`` now returns the **full message** which was just
   sent.

New way to work with updates (v0.13.2)
======================================

*Published at 2017/09/08*

This update brings a new way to work with updates, and it's begging for
your **feedback**, or better names or ways to do what you can do now.

Please refer to the `wiki/Usage
Modes <https://github.com/LonamiWebs/Telethon/wiki/Usage-Modes>`__ for
an in-depth description on how to work with updates now. Notice that you
cannot invoke requests from within handlers anymore, only the
``v.0.13.1`` patch allowed you to do so.

Bug fixes
~~~~~~~~~

- Periodic pings are back.
- The username regex mentioned on ``UsernameInvalidError`` was invalid,
  but it has now been fixed.
- Sending a message to a phone number was failing because the type used
  for a request had changed on layer 71.
- CDN downloads weren't working properly, and now a few patches have been
  applied to ensure more reliability, although I couldn't personally test
  this, so again, report any feedback.

Invoke other requests from within update callbacks (v0.13.1)
============================================================

*Published at 2017/09/04*

.. warning::

    This update brings some big changes to the update system,
    so please read it if you work with them!

A silly "bug" which hadn't been spotted has now been fixed. Now you can
invoke other requests from within your update callbacks. However **this
is not advised**. You should post these updates to some other thread,
and let that thread do the job instead. Invoking a request from within a
callback will mean that, while this request is being invoked, no other
things will be read.

Internally, the generated code now resides under a *lot* less files,
simply for the sake of avoiding so many unnecessary files. The generated
code is not meant to be read by anyone, simply to do its job.

Unused attributes have been removed from the ``TLObject`` class too, and
``.sign_up()`` returns the user that just logged in in a similar way to
``.sign_in()`` now.

Connection modes (v0.13)
========================

*Published at 2017/09/04*

+-----------------------+
| Scheme layer used: 71 |
+-----------------------+

The purpose of this release is to denote a big change, now you can
connect to Telegram through different `**connection
modes** <https://github.com/LonamiWebs/Telethon/blob/v0.13/telethon/network/connection.py>`__.
Also, a **second thread** will *always* be started when you connect a
``TelegramClient``, despite whether you'll be handling updates or
ignoring them, whose sole purpose is to constantly read from the
network.

The reason for this change is as simple as *"reading and writing
shouldn't be related"*. Even when you're simply ignoring updates, this
way, once you send a request you will only need to read the result for
the request. Whatever Telegram sent before has already been read and
outside the buffer.

.. additions-2:

Additions
---------

-  The mentioned different connection modes, and a new thread.
-  You can modify the ``Session`` attributes through the
   ``TelegramClient`` constructor (using ``**kwargs``).
-  ``RPCError``\ 's now belong to some request you've made, which makes
   more sense.
-  ``get_input_*`` now handles ``None`` (default) parameters more
   gracefully (it used to crash).

.. enhancements-4:

Enhancements
------------

-  The low-level socket doesn't use a handcrafted timeout anymore, which
   should benefit by avoiding the arbitrary ``sleep(0.1)`` that there
   used to be.
-  ``TelegramClient.sign_in`` will call ``.send_code_request`` if no
   ``code`` was provided.

Deprecation
-----------

-  ``.sign_up`` does *not* take a ``phone`` argument anymore. Change
   this or you will be using ``phone`` as ``code``, and it will fail!
   The definition looks like
   ``def sign_up(self, code, first_name, last_name='')``.
-  The old ``JsonSession`` finally replaces the original ``Session``
   (which used pickle). If you were overriding any of these, you should
   only worry about overriding ``Session`` now.

Added verification for CDN file (v0.12.2)
=========================================

*Published at 2017/08/28*

Since the Content Distributed Network (CDN) is not handled by Telegram
itself, the owners may tamper these files. Telegram sends their sha256
sum for clients to implement this additional verification step, which
now the library has. If any CDN has altered the file you're trying to
download, ``CdnFileTamperedError`` will be raised to let you know.

Besides this. ``TLObject.stringify()`` was showing bytes as lists (now
fixed) and RPC errors are reported by default:

    In an attempt to help everyone who works with the Telegram API,
    Telethon will by default report all Remote Procedure Call errors to
    `PWRTelegram <https://pwrtelegram.xyz/>`__, a public database anyone can
    query, made by `Daniil <https://github.com/danog>`__. All the information
    sent is a GET request with the error code, error message and method used.


.. note::

    If you still would like to opt out, simply set
    ``client.session.report_errors = False`` to disable this feature.
    However Daniil would really thank you if you helped him (and everyone)
    by keeping it on!

CDN support (v0.12.1)
=====================

*Published at 2017/08/24*

The biggest news for this update are that downloading media from CDN's
(you'll often encounter this when working with popular channels) now
**works**.

Bug fixes
~~~~~~~~~

- The method used to download documents crashed because
  two lines were swapped.
- Determining the right path when downloading any file was
  very weird, now it's been enhanced.
- The ``.sign_in()`` method didn't support integer values for the code!
  Now it does again.

Some important internal changes are that the old way to deal with RSA
public keys now uses a different module instead the old strange
hand-crafted version.

Hope the new, super simple ``README.rst`` encourages people to use
Telethon and make it better with either suggestions, or pull request.
Pull requests are *super* appreciated, but showing some support by
leaving a star also feels nice ⭐️.

Newbie friendly update (v0.12)
==============================

*Published at 2017/08/22*

+-----------------------+
| Scheme layer used: 70 |
+-----------------------+

This update is overall an attempt to make Telethon a bit more user
friendly, along with some other stability enhancements, although it
brings quite a few changes.

Breaking changes
----------------

-  The ``TelegramClient`` methods ``.send_photo_file()``,
   ``.send_document_file()`` and ``.send_media_file()`` are now a
   **single method** called ``.send_file()``. It's also important to
   note that the **order** of the parameters has been **swapped**: first
   to *who* you want to send it, then the file itself.

-  The same applies to ``.download_msg_media()``, which has been renamed
   to ``.download_media()``. The method now supports a ``Message``
   itself too, rather than only ``Message.media``. The specialized
   ``.download_photo()``, ``.download_document()`` and
   ``.download_contact()`` still exist, but are private.

Additions
---------

-  Updated to **layer 70**!
-  Both downloading and uploading now support **stream-like objects**.
-  A lot **faster initial connection** if ``sympy`` is installed (can be
   installed through ``pip``).
-  ``libssl`` will also be used if available on your system (likely on
   Linux based systems). This speed boost should also apply to uploading
   and downloading files.
-  You can use a **phone number** or an **username** for methods like
   ``.send_message()``, ``.send_file()``, and all the other quick-access
   methods provided by the ``TelegramClient``.

.. bug-fixes-5:

Bug fixes
---------

-  Crashing when migrating to a new layer and receiving old updates
   should not happen now.
-  ``InputPeerChannel`` is now casted to ``InputChannel`` automtically
   too.
-  ``.get_new_msg_id()`` should now be thread-safe. No promises.
-  Logging out on macOS caused a crash, which should be gone now.
-  More checks to ensure that the connection is flagged correctly as
   either connected or not.

.. note::

   Downloading files from CDN's will **not work** yet (something new
   that comes with layer 70).

--------------

That's it, any new idea or suggestion about how to make the project even
more friendly is highly appreciated.

.. note::

    Did you know that you can pretty print any result Telegram returns
    (called ``TLObject``\ 's) by using their ``.stringify()`` function?
    Great for debugging!

get_input_* now works with vectors (v0.11.5)
=============================================

*Published at 2017/07/11*

Quick fix-up of a bug which hadn't been encountered until now. Auto-cast
by using ``get_input_*`` now works.

get_input_* everywhere (v0.11.4)
=================================

*Published at 2017/07/10*

For some reason, Telegram doesn't have enough with the
`InputPeer <https://lonamiwebs.github.io/Telethon/types/input_peer.html>`__.
There also exist
`InputChannel <https://lonamiwebs.github.io/Telethon/types/input_channel.html>`__
and
`InputUser <https://lonamiwebs.github.io/Telethon/types/input_user.html>`__!
You don't have to worry about those anymore, it's handled internally
now.

Besides this, every Telegram object now features a new default
``.__str__`` look, and also a `.stringify()
method <https://github.com/LonamiWebs/Telethon/commit/8fd0d7eadd944ff42e18aaf06228adc7aba794b5>`__
to pretty format them, if you ever need to inspect them.

The library now uses `the DEBUG
level <https://github.com/LonamiWebs/Telethon/commit/1f7ac7118750ed84e2165dce9c6aca2e6ea0c6a4>`__
everywhere, so no more warnings or information messages if you had
logging enabled.

The ``no_webpage`` parameter from ``.send_message`` `has been
renamed <https://github.com/LonamiWebs/Telethon/commit/0119a006585acd1a1a9a8901a21bb2f193142cfe>`__
to ``link_preview`` for clarity, so now it does the opposite (but has a
clearer intention).

Quick .send_message() fix (v0.11.3)
===================================

*Published at 2017/07/05*

A very quick follow-up release to fix a tiny bug with
``.send_message()``, no new features.

Callable TelegramClient (v0.11.2)
=================================

*Published at 2017/07/04*

+-----------------------+
| Scheme layer used: 68 |
+-----------------------+

There is a new preferred way to **invoke requests**, which you're
encouraged to use:

.. code:: python

    # New!
    result = client(SomeRequest())

    # Old.
    result = client.invoke(SomeRequest())

Existing code will continue working, since the old ``.invoke()`` has not
been deprecated.

When you ``.create_new_connection()``, it will also handle
``FileMigrateError``\ 's for you, so you don't need to worry about those
anymore.

.. bugs-fixed-3:

Bugs fixes
~~~~~~~~~~

-  Fixed some errors when installing Telethon via ``pip`` (for those
   using either source distributions or a Python version ≤ 3.5).
-  ``ConnectionResetError`` didn't flag sockets as closed, but now it
   does.

On a more technical side, ``msg_id``\ 's are now more accurate.

Improvements to the updates (v0.11.1)
=====================================

*Published at 2017/06/24*

Receiving new updates shouldn't miss any anymore, also, periodic pings
are back again so it should work on the long run.

On a different order of things, ``.connect()`` also features a timeout.
Notice that the ``timeout=`` is **not** passed as a **parameter**
anymore, and is instead specified when creating the ``TelegramClient``.

Bug fixes
~~~~~~~~~

- Fixed some name class when a request had a ``.msg_id`` parameter.
- The correct amount of random bytes is now used in DH request
- Fixed ``CONNECTION_APP_VERSION_EMPTY`` when using temporary sessions.
- Avoid connecting if already connected.

Support for parallel connections (v0.11)
========================================

*Published at 2017/06/16*

*This update brings a lot of changes, so it would be nice if you could*
**read the whole change log**!

Breaking changes
----------------

-  Every Telegram error has now its **own class**, so it's easier to
   fine-tune your ``except``\ 's.
-  Markdown parsing is **not part** of Telethon itself anymore, although
   there are plans to support it again through a some external module.
-  The ``.list_sessions()`` has been moved to the ``Session`` class
   instead.
-  The ``InteractiveTelegramClient`` is **not** shipped with ``pip``
   anymore.

Additions
---------

-  A new, more **lightweight class** has been added. The
   ``TelegramBareClient`` is now the base of the normal
   ``TelegramClient``, and has the most basic features.
-  New method to ``.create_new_connection()``, which can be ran **in
   parallel** with the original connection. This will return the
   previously mentioned ``TelegramBareClient`` already connected.
-  Any file object can now be used to download a file (for instance, a
   ``BytesIO()`` instead a file name).
-  Vales like ``random_id`` are now **automatically inferred**, so you
   can save yourself from the hassle of writing
   ``generate_random_long()`` everywhere. Same applies to
   ``.get_input_peer()``, unless you really need the extra performance
   provided by skipping one ``if`` if called manually.
-  Every type now features a new ``.to_dict()`` method.

.. bug-fixes-6:

Bug fixes
---------

-  Received errors are acknowledged to the server, so they don't happen
   over and over.
-  Downloading media on different data centers is now up to **x2
   faster**, since there used to be an ``InvalidDCError`` for each file
   part tried to be downloaded.
-  Lost messages are now properly skipped.
-  New way to handle the **result of requests**. The old ``ValueError``
   "*The previously sent request must be resent. However, no request was
   previously sent (possibly called from a different thread).*" *should*
   not happen anymore.

Internal changes
----------------

-  Some fixes to the ``JsonSession``.
-  Fixed possibly crashes if trying to ``.invoke()`` a ``Request`` while
   ``.reconnect()`` was being called on the ``UpdatesThread``.
-  Some improvements on the ``TcpClient``, such as not switching between
   blocking and non-blocking sockets.
-  The code now uses ASCII characters only.
-  Some enhancements to ``.find_user_or_chat()`` and
   ``.get_input_peer()``.

JSON session file (v0.10.1)
===========================

*Published at 2017/06/07*

This version is primarily for people to **migrate** their ``.session``
files, which are *pickled*, to the new *JSON* format. Although slightly
slower, and a bit more vulnerable since it's plain text, it's a lot more
resistant to upgrades.

.. warning::

    You **must** upgrade to this version before any higher one if you've
    used Telethon ≤ v0.10. If you happen to upgrade to an higher version,
    that's okay, but you will have to manually delete the ``*.session`` file,
    and logout from that session from an official client.

Additions
~~~~~~~~~

- New ``.get_me()`` function to get the **current** user.
- ``.is_user_authorized()`` is now more reliable.
- New nice button to copy the ``from telethon.tl.xxx.yyy import Yyy``
  on the online documentation.
- **More error codes** added to the ``errors`` file.

Enhancements
~~~~~~~~~~~~

- Everything on the documentation is now, theoretically, **sorted
  alphabetically**.
- No second thread is spawned unless one or more update handlers are added.

Full support for different DCs and ++stable (v0.10)
===================================================

*Published at 2017/06/03*

Working with **different data centers** finally *works*! On a different
order of things, **reconnection** is now performed automatically every
time Telegram decides to kick us off their servers, so now Telethon can
really run **forever and ever**! In theory.

Enhancements
~~~~~~~~~~~~

-  **Documentation** improvements, such as showing the return type.
-  The ``msg_id too low/high`` error should happen **less often**, if
   any.
-  Sleeping on the main thread is **not done anymore**. You will have to
   ``except FloodWaitError``\ 's.
-  You can now specify your *own application version*, device model,
   system version and language code.
-  Code is now more *pythonic* (such as making some members private),
   and other internal improvements (which affect the **updates
   thread**), such as using ``logger`` instead a bare ``print()`` too.

This brings Telethon a whole step closer to ``v1.0``, though more things
should preferably be changed.

Stability improvements (v0.9.1)
===============================

*Published at 2017/05/23*

Telethon used to crash a lot when logging in for the very first time.
The reason for this was that the reconnection (or dead connections) were
not handled properly. Now they are, so you should be able to login
directly, without needing to delete the ``*.session`` file anymore.
Notice that downloading from a different DC is still a WIP.

Enhancements
~~~~~~~~~~~~

- Updates thread is only started after a successful login.
- Files meant to be ran by the user now use **shebangs** and
  proper permissions.
- In-code documentation now shows the returning type.
- **Relative import** is now used everywhere, so you can rename
  ``telethon`` to anything else.
- **Dead connections** are now **detected** instead entering an infinite loop.
- **Sockets** can now be **closed** (and re-opened) properly.
- Telegram decided to update the layer 66 without increasing the number.
  This has been fixed and now we're up-to-date again.

General improvements (v0.9)
===========================

*Published at 2017/05/19*

+-----------------------+
| Scheme layer used: 66 |
+-----------------------+

Additions
~~~~~~~~~

- The **documentation**, available online
  `here <https://lonamiwebs.github.io/Telethon/>`__, has a new search bar.
- Better **cross-thread safety** by using ``threading.Event``.
- More improvements for running Telethon during a **long period of time**.

Bug fixes
~~~~~~~~~

- **Avoid a certain crash on login** (occurred if an unexpected object
  ID was received).
- Avoid crashing with certain invalid UTF-8 strings.
- Avoid crashing on certain terminals by using known ASCII characters
  where possible.
- The ``UpdatesThread`` is now a daemon, and should cause less issues.
- Temporary sessions didn't actually work (with ``session=None``).

Internal changes
~~~~~~~~~~~~~~~~

- ``.get_dialogs(count=`` was renamed to ``.get_dialogs(limit=``.

Bot login and proxy support (v0.8)
==================================

*Published at 2017/04/14*

Additions
~~~~~~~~~

-  **Bot login**, thanks to @JuanPotato for hinting me about how to do
   it.
-  **Proxy support**, thanks to @exzhawk for implementing it.
-  **Logging support**, used by passing ``--telethon-log=DEBUG`` (or
   ``INFO``) as a command line argument.

Bug fixes
~~~~~~~~~

- Connection fixes, such as avoiding connection until ``.connect()`` is
  explicitly invoked.
- Uploading big files now works correctly.
- Fix uploading big files.
- Some fixes on the updates thread, such as correctly sleeping when required.

Long-run bug fix (v0.7.1)
=========================

*Published at 2017/02/19*

If you're one of those who runs Telethon for a long time (more than 30
minutes), this update by @strayge will be great for you. It sends
periodic pings to the Telegram servers so you don't get disconnected and
you can still send and receive updates!

Two factor authentication (v0.7)
================================

*Published at 2017/01/31*

+-----------------------+
| Scheme layer used: 62 |
+-----------------------+

If you're one of those who love security the most, these are good news.
You can now use two factor authentication with Telethon too! As internal
changes, the coding style has been improved, and you can easily use
custom session objects, and various little bugs have been fixed.

Updated pip version (v0.6)
==========================

*Published at 2016/11/13*

+-----------------------+
| Scheme layer used: 57 |
+-----------------------+

This release has no new major features. However, it contains some small
changes that make using Telethon a little bit easier. Now those who have
installed Telethon via ``pip`` can also take advantage of changes, such
as less bugs, creating empty instances of ``TLObjects``, specifying a
timeout and more!

Ready, pip, go! (v0.5)
======================

*Published at 2016/09/18*

Telethon is now available as a **`Python
package <https://pypi.python.org/pypi?name=Telethon>`__**! Those are
really exciting news (except, sadly, the project structure had to change
*a lot* to be able to do that; but hopefully it won't need to change
much more, any more!)

Not only that, but more improvements have also been made: you're now
able to both **sign up** and **logout**, watch a pretty
"Uploading/Downloading… x%" progress, and other minor changes which make
using Telethon **easier**.

Made InteractiveTelegramClient cool (v0.4)
==========================================

*Published at 2016/09/12*

Yes, really cool! I promise. Even though this is meant to be a
*library*, that doesn't mean it can't have a good *interactive client*
for you to try the library out. This is why now you can do many, many
things with the ``InteractiveTelegramClient``:

- **List dialogs** (chats) and pick any you wish.
- **Send any message** you like, text, photos or even documents.
- **List** the **latest messages** in the chat.
- **Download** any message's media (photos, documents or even contacts!).
- **Receive message updates** as you talk (i.e., someone sent you a message).

It actually is an usable-enough client for your day by day. You could
even add ``libnotify`` and pop, you're done! A great cli-client with
desktop notifications.

Also, being able to download and upload media implies that you can do
the same with the library itself. Did I need to mention that? Oh, and
now, with even less bugs! I hope.

Media revolution and improvements to update handling! (v0.3)
============================================================

*Published at 2016/09/11*

Telegram is more than an application to send and receive messages. You
can also **send and receive media**. Now, this implementation also gives
you the power to upload and download media from any message that
contains it! Nothing can now stop you from filling up all your disk
space with all the photos! If you want to, of course.

Handle updates in their own thread! (v0.2)
==========================================

*Published at 2016/09/10*

This version handles **updates in a different thread** (if you wish to
do so). This means that both the low level ``TcpClient`` and the
not-so-low-level ``MtProtoSender`` are now multi-thread safe, so you can
use them with more than a single thread without worrying!

This also implies that you won't need to send a request to **receive an
update** (is someone typing? did they send me a message? has someone
gone offline?). They will all be received **instantly**.

Some other cool examples of things that you can do: when someone tells
you "*Hello*", you can automatically reply with another "*Hello*"
without even needing to type it by yourself :)

However, be careful with spamming!! Do **not** use the program for that!

First working alpha version! (v0.1)
===================================

*Published at 2016/09/06*

+-----------------------+
| Scheme layer used: 55 |
+-----------------------+

There probably are some bugs left, which haven't yet been found.
However, the majority of code works and the application is already
usable! Not only that, but also uses the latest scheme as of now *and*
handles way better the errors. This tag is being used to mark this
release as stable enough.
