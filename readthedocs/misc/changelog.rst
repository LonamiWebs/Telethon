.. _changelog:


===========================
Changelog (Version History)
===========================


This page lists all the available versions of the library,
in chronological order. You should read this when upgrading
the library to know where your code can break, and where
it can take advantage of new goodies!

.. contents:: List of All Versions

Rushed release to fix login (v1.24)
===================================

+------------------------+
| Scheme layer used: 133 |
+------------------------+

This is a rushed release. It contains a layer recent enough to not fail with
``UPDATE_APP_TO_LOGIN``, but still not the latest, to avoid breaking more
than necessary.

Breaking Changes
~~~~~~~~~~~~~~~~

* The biggest change is user identifiers (and chat identifiers, and others)
  **now use up to 64 bits**, rather than 32. If you were storing them in some
  storage with fixed size, you may need to update (such as database tables
  storing only integers).

There have been other changes which I currently don't have the time to document.
You can refer to the following link to see them early:
https://github.com/LonamiWebs/Telethon/compare/v1.23.0...v1.24.0


New schema and bug fixes (v1.23)
================================

+------------------------+
| Scheme layer used: 130 |
+------------------------+

`View new and changed raw API methods <https://diff.telethon.dev/?from=129&to=130>`__.

Enhancements
~~~~~~~~~~~~

* `client.pin_message() <telethon.client.messages.MessageMethods.pin_message>`
  can now pin on a single side in PMs.
* Iterating participants should now be less expensive floodwait-wise.

Bug fixes
~~~~~~~~~

* The QR login URL was being encoded incorrectly.
* ``force_document`` was being ignored in inline queries for document.
* ``manage_call`` permission was accidentally set to ``True`` by default.

New schema and bug fixes (v1.22)
================================

+------------------------+
| Scheme layer used: 129 |
+------------------------+

`View new and changed raw API methods <https://diff.telethon.dev/?from=125&to=129>`__.

Enhancements
~~~~~~~~~~~~

* You can now specify a message in `client.get_stats()
  <telethon.client.chats.ChatMethods.get_stats>`.
* Metadata extraction from audio files with ``hachoir`` now recognises "artist".
* Get default chat permissions by not supplying a user to `client.get_permissions()
  <telethon.client.chats.ChatMethods.get_permissions>`.
* You may now use ``thumb`` when editing messages.

Bug fixes
~~~~~~~~~

* Fixes regarding bot markup in messages.
* Gracefully handle :tl:`ChannelForbidden` in ``get_sender``.

And from v1.21.1:

* ``file.width`` and ``.height`` was not working correctly in photos.
* Raw API was mis-interpreting ``False`` values on boolean flag parameters.

New schema and QoL improvements (v1.21)
=======================================

+------------------------+
| Scheme layer used: 125 |
+------------------------+

`View new and changed raw API methods <https://diff.telethon.dev/?from=124&to=125>`__.

Not many changes in this release, mostly the layer change. Lately quite a few
people have been reporting `TypeNotFoundError`, which occurs when the server
**sends types that it shouldn't**. This can happen when Telegram decides to
add a new, incomplete layer, and then they change the layer without bumping
the layer number (so some constructor IDs no longer match and the error
occurs). This layer change
`should fix it <https://github.com/LonamiWebs/Telethon/issues/1724>`__.

Additions
~~~~~~~~~

* `Message.click() <telethon.tl.custom.message.Message.click>` now supports
  a ``password`` parameter, needed when doing things like changing the owner
  of a bot via `@BotFather <https://t.me/BotFather>`__.

Enhancements
~~~~~~~~~~~~

* ``tgcrypto`` will now be used for encryption when installed.

Bug fixes
~~~~~~~~~

* `Message.edit <telethon.tl.custom.message.Message.edit>` wasn't working in
  your own chat on events other than ``NewMessage``.
* `client.delete_dialog() <telethon.client.dialogs.DialogMethods.delete_dialog>`
  was not working on chats.
* ``events.UserUpdate`` should now handle channels' typing status.
* :tl:`InputNotifyPeer` auto-cast should now work on other ``TLObject``.
* For some objects, ``False`` was not correctly serialized.


New schema and QoL improvements (v1.20)
=======================================

+------------------------+
| Scheme layer used: 124 |
+------------------------+

`View new and changed raw API methods <https://diff.telethon.dev/?from=122&to=124>`__.

A bit late to the party, but Telethon now offers a convenient way to comment
on channel posts. It works very similar to ``reply_to``:

.. code-block:: python

    client.send_message(channel, 'Great update!', comment_to=1134)

This code will leave a comment to the channel post with ID ``1134`` in
``channel``.

In addition, the library now logs warning or error messages to ``stderr`` by
default! You no longer should be left wondering "why isn't my event handler
working" if you forgot to configure logging. It took so long for this change
to arrive because nobody noticed that Telethon was using a
``logging.NullHandler`` when it really shouldn't have.

If you want the old behaviour of no messages being logged, you can configure
`logging` to ``CRITICAL`` severity:

.. code-block:: python

    import logging
    logging.basicConfig(level=logging.CRITICAL)

This is not considered a breaking change because ``stderr`` should only be
used for logging purposes, not to emit information others may consume (use
``stdout`` for that).

Additions
~~~~~~~~~

* New ``comment_to`` parameter in `client.send_message()
  <telethon.client.messages.MessageMethods.send_message>`, and
  `client.send_file() <telethon.client.uploads.UploadMethods.send_file>`
  to comment on channel posts.

Enhancements
~~~~~~~~~~~~

* ``utils.resolve_invite_link`` handles the newer link format.
* Downloading files now retries once on `TimeoutError`, which has been
  happening recently. It is not guaranteed to work, but it should help.
* Sending albums of photo URLs is now supported.
* EXIF metadata is respected when automatically resizing photos, so the
  orientation information should no longer be lost.
* Downloading a thumbnail by index should now use the correct size ordering.

Bug fixes
~~~~~~~~~

* Fixed a `KeyError` on certain cases with ``Conversation``.
* Thumbnails should properly render on more clients. Installing ``hachoir``
  may help.
* Message search was broken when using a certain combination of parameters.
* ``utils.resolve_id`` was misbehaving with some identifiers.
* Fix ``TypeNotFoundError`` was not being propagated, causing deadlocks.
* Invoking multiple requests at once with ``ordered=True`` was deadlocking.


New raw API call methods (v1.19)
================================

+------------------------+
| Scheme layer used: 122 |
+------------------------+

Telegram has had group calls for some weeks now. This new version contains the
raw API methods needed to initiate and manage these group calls, however, the
library will likely **not offer ways to stream audio directly**.

Telethon's focus is being an asyncio-based, pure-Python implementation to
interact with Telegram's API. Streaming audio is beyond the current scope of
the project and would be a big undertaking.

However, that doesn't mean calls are not possible with Telethon. If you want
to help design a Python library to perform audio calls, which can then be used
with Telethon (so you can use Telethon + that new library to perform calls
with Telethon), please refer to `@pytgcallschat <https://t.me/pytgcallschat/>`__
and join the relevant chat to discuss and help with the implementation!

The above message was also `posted in the official Telegram group
<https://t.me/TelethonChat/284717>`__, if you wish to discuss it further.

With that out of the way, let's list the additions and bug fixes in this
release:

Additions
~~~~~~~~~

* New ``has_left`` property for user permissions on `client.get_permissions()
  <telethon.client.chats.ChatMethods.get_permissions>`.

Enhancements
~~~~~~~~~~~~

* Updated documentation and list of known RPC errors.
* The library now treats a lack of ping responses as a network error.
* `client.kick_participant() <telethon.client.chats.ChatMethods.kick_participant>`
  now returns the service message about the user being kicked, so you can
  delete it.

Bug fixes
~~~~~~~~~

* When editing inline messages, the text parameter is preferred if provided.
* Additional senders are unconditionally disconnected when disconnecting the
  main client, which should reduce the amount of asyncio warnings.
* Automatic reconnection with no retries was failing.
* :tl:`PhotoPathSize` is now ignored when determining a download size, since
  this "size" is not a JPEG thumbnail unlike the rest.
* `events.ChatAction <telethon.events.chataction.ChatAction>` should misbehave
  less.


New layer and QoL improvements (v1.18)
======================================

+------------------------+
| Scheme layer used: 120 |
+------------------------+

Mostly fixes, and added some new things that can be done in this new layer.

For proxy users, a pull request was merged that will use the ``python-socks``
library when available for proxy support. This library natively supports
`asyncio`, so it should work better than the old ``pysocks``. ``pysocks`` will
still be used if the new library is not available, and both will be handled
transparently by Telethon so you don't need to worry about it.

Additions
~~~~~~~~~

* New `client.set_proxy()
  <telethon.client.telegrambaseclient.TelegramBaseClient.set_proxy>` method
  which lets you change the proxy without recreating the client. You will need
  to reconnect for it to take effect, but you won't need to recreate the
  client. This is also an external contribution.
* New method to unpin messages `client.unpin_message()
  <telethon.client.messages.MessageMethods.unpin_message>`.

Enhancements
~~~~~~~~~~~~

* Empty peers are excluded from the list of dialogs.
* If the ``python-socks`` library is installed (new optional requirement), it
  will be used instead of ``pysocks`` for proxy support. This should fix some
  issues with proxy timeouts, because the new library natively supports
  `asyncio`.
* `client.send_file() <telethon.client.uploads.UploadMethods.send_file>` will
  now group any media type, instead of sending non-image documents separatedly.
  This lets you create music albums, for example.
* You can now search messages with a ``from_user`` that's not a user. This is
  a Telegram feature, we know the name isn't great, but backwards-compatibility
  has to be kept.

Bug fixes
~~~~~~~~~

* Fixes related to conversation timeouts.
* Large dates (over year 2038) now wrap around a 32-bit integer, which is the
  only way we can represent them to Telegram. Even if "wrong", it makes things
  not crash, and it's the best we can do with 32-bit dates.
* The library was accidentally using a deprecated argument in one of its
  friendly methods, producing a warning.
* Improvements to the way marked IDs are parsed.
* ``SlowModeWaitError`` floods are no longer cached.
* Getting the buttons for a message could fail sometimes.
* Getting the display name for "forbidden" chats now works.
* Better handling of errors in some internal methods.


Channel comments and Anonymous Admins (v1.17)
=============================================

+------------------------+
| Scheme layer used: 119 |
+------------------------+

New minor version, new layer change! This time is a good one to remind every
consumer of Python libraries that **you should always specify fixed versions
of your dependencies**! If you're using a ``requirements.txt`` file and you
want to stick with the old version (or any version) for the time being, you
can `use the following syntax <https://pip.pypa.io/en/stable/user_guide/>`__:

.. code-block:: text

    telethon~=1.16.0

This will install any version compatible with the written version (so, any in
the ``1.16`` series). Patch releases will never break your code (and if they
do, it's a bug). You can also use that syntax in ``pip install``. Your code
can't know what new versions will look like, so saying it will work with all
versions is a lie and will cause issues.

The reason to bring this up is that Telegram has changed things again, and
with the introduction of anonymous administrators and channel comments, the
sender of a message may not be a :tl:`User`! To accomodate for this, the field
is now a :tl:`Peer` and not `int`. As a reminder, it's always a good idea to
use Telethon's friendly methods and custom properties, which have a higher
stability guarantee than accessing raw API fields.

Even if you don't update, your code will still need to account for the fact
that the sender of a message might be one of the accounts Telegram introduced
to preserve backwards compatibility, because this is a server-side change, so
it's better to update and not lag behind. As it's mostly just a single person
driving the project on their free time, bug-fixes are not backported.

This version also updates the format of SQLite sessions (the default), so
after upgrading and using an old session, the session will be updated, which
means trying to use it back in older versions of the library won't work.

For backwards-compatibility sake, the library has introduced the properties
`Message.reply_to_msg_id <telethon.tl.custom.message.Message.reply_to_msg_id>`
and `Message.to_id <telethon.tl.custom.message.Message.to_id>` that behave
like they did before (Telegram has renamed and changed how these fields work).


Breaking Changes
~~~~~~~~~~~~~~~~

* ``Message.from_id`` is now a :tl:`Peer`, not `int`! If you want the marked
  sender ID (much like old behaviour), replace all uses of ``.from_id`` with
  ``.sender_id``. This will mostly work, but of course in old and new versions
  you have to account for the fact that this sender may no longer be a user.
* You can no longer assign to `Message.reply_to_msg_id
  <telethon.tl.custom.message.Message.reply_to_msg_id>` and `Message.to_id
  <telethon.tl.custom.message.Message.to_id>` because these are now properties
  that offer a "view" to the real value from a different field.
* Answering inline queries with a ``photo`` or ``document`` will now send the
  photo or document used in the resulting message by default. Not sending the
  media was technically a bug, but some people may be relying on this old
  behaviour. You can use the old behaviour with ``include_media=False``.

Additions
~~~~~~~~~

* New ``raise_last_call_error`` parameter in the client constructor to raise
  the same error produced by the last failing call, rather than a generic
  `ValueError`.
* New ``formatting_entities`` parameter in `client.send_message()
  <telethon.client.messages.MessageMethods.send_message>`, and
  `client.send_file() <telethon.client.uploads.UploadMethods.send_file>`
  to bypass the parse mode and manually specify the formatting entities.
* New `client.get_permissions() <telethon.client.chats.ChatMethods.get_permissions>`
  method to query a participant's permissions in a group or channel. This
  request is slightly expensive in small group chats because it has to fetch
  the entire chat to check just a user, so use of a cache is advised.
* `Message.click() <telethon.tl.custom.message.Message.click>` now works on
  normal polls!
* New ``local_addr`` parameter in the client constructor to use a specific
  local network address when connecting to Telegram.
* `client.inline_query() <telethon.client.bots.BotMethods.inline_query>` now
  lets you specify the chat where the query is being made from, which some
  bots need to provide certain functionality.
* You can now get comments in a channel post with the ``reply_to`` parameter in
  `client.iter_messages() <telethon.client.messages.MessageMethods.iter_messages>`.
  Comments are messages that "reply to" a specific channel message, hence the
  name (which is consistent with how Telegram's API calls it).

Enhancements
~~~~~~~~~~~~

* Updated documentation and list of known errors.
* If ``hachoir`` is available, the file metadata can now be extracted from
  streams and in-memory bytes.
* The default parameters used to initialize a connection now match the format
  of those used by Telegram Desktop.
* Specifying 0 retries will no longer cause the library to attempt to reconnect.
* The library should now be able to reliably download very large files.
* Global search should work more reliably now.
* Old usernames are evicted from cache, so getting entities by cached username
  should now be more reliable.
* Slightly less noisy logs.
* Stability regarding transport-level errors (transport flood, authorization
  key not found) should be improved. In particular, you should no longer be
  getting unnecessarily logged out.
* Reconnection should no longer occur if the client gets logged out (for
  example, another client revokes the session).

Bug fixes
~~~~~~~~~

* In some cases, there were issues when using `events.Album
  <telethon.events.album.Album>` together with `events.Raw
  <telethon.events.raw.Raw>`.
* For some channels, one of their channel photos would not show up in
  `client.iter_profile_photos() <telethon.client.chats.ChatMethods.iter_profile_photos>`.
* In some cases, a request that failed to be sent would be forgotten, causing
  the original caller to be "locked" forever for a response that would never
  arrive. Failing requests should now consistently be automatically re-sent.
* The library should more reliably handle certain updates with "empty" data.
* Sending documents in inline queries should now work fine.
* Manually using `client.sign_up <telethon.client.auth.AuthMethods.sign_up>`
  should now work correctly, instead of claiming "code invalid".

Special mention to some of the other changes in the 1.16.x series:

* The ``thumb`` for ``download_media`` now supports both `str` and :tl:`VideoSize`.
* Thumbnails are sorted, so ``-1`` is always the largest.


Bug Fixes (v1.16.1)
===================

The last release added support to ``force_file`` on any media, including
things that were not possible before like ``.webp`` files. However, the
``force_document`` toggle commonly used for photos was applied "twice"
(one told the library to send it as a document, and then to send that
document as file), which prevented Telegram for analyzing the images. Long
story short, sending files to the stickers bot stopped working, but that's
been fixed now, and sending photos as documents include the size attribute
again as long as Telegram adds it.

Enhancements
~~~~~~~~~~~~

* When trying to `client.start() <telethon.client.auth.AuthMethods.start>` to
  another account if you were previously logged in, the library will now warn
  you because this is probably not intended. To avoid the warning, make sure
  you're logging in to the right account or logout from the other first.
* Sending a copy of messages with polls will now work when possible.
* The library now automatically retries on inter-dc call errors (which occur
  when Telegram has internal issues).

Bug Fixes
~~~~~~~~~

* The aforementioned issue with ``force_document``.
* Square brackets removed from IPv6 addresses. This may fix IPv6 support.


Channel Statistics (v1.16)
==========================

+------------------------+
| Scheme layer used: 116 |
+------------------------+

The newest Telegram update has a new method to also retrieve megagroup
statistics, which can now be used with `client.get_stats()
<telethon.client.chats.ChatMethods.get_stats>`. This way you'll be able
to access the raw data about your channel or megagroup statistics.

The maximum file size limit has also been increased to 2GB on the server,
so you can send even larger files.

Breaking Changes
~~~~~~~~~~~~~~~~

* Besides the obvious layer change, the ``loop`` argument **is now ignored**.
  It has been deprecated since Python 3.8 and will be removed in Python 3.10,
  and also caused some annoying warning messages when using certain parts of
  the library. If you were (incorrectly) relying on using a different loop
  from the one that was set, things may break.

Enhancements
~~~~~~~~~~~~

* `client.upload_file() <telethon.client.uploads.UploadMethods.upload_file>`
  now works better when streaming files (anything that has a ``.read()``),
  instead of reading it all into memory when possible.


QR login (v1.15)
================

*Published at 2020/07/04*

+------------------------+
| Scheme layer used: 114 |
+------------------------+

The library now has a friendly method to perform QR-login, as detailed in
https://core.telegram.org/api/qr-login. It won't generate QR images, but it
provides a way for you to easily do so with any other library of your choice.

Additions
~~~~~~~~~

* New `client.qr_login() <telethon.client.auth.AuthMethods.qr_login>`.
* `message.click <telethon.tl.custom.message.Message.click>` now lets you
  click on buttons requesting phone or location.

Enhancements
~~~~~~~~~~~~

* Updated documentation and list of known errors.
* `events.Album <telethon.events.album.Album>` should now handle albums from
  different data centers more gracefully.
* `client.download_file()
  <telethon.client.downloads.DownloadMethods.download_file>` now supports
  `pathlib.Path` as the destination.

Bug fixes
~~~~~~~~~

* No longer crash on updates received prior to logging in.
* Server-side changes caused clicking on inline buttons to trigger a different
  error, which is now handled correctly.


Minor quality of life improvements (v1.14)
==========================================

*Published at 2020/05/26*

+------------------------+
| Scheme layer used: 113 |
+------------------------+

Some nice things that were missing, along with the usual bug-fixes.

Additions
~~~~~~~~~

* New `Message.dice <telethon.tl.custom.message.Message.dice>` property.
* The ``func=`` parameter of events can now be an ``async`` function.

Bug fixes
~~~~~~~~~

* Fixed `client.action() <telethon.client.chats.ChatMethods.action>`
  having an alias wrong.
* Fixed incorrect formatting of some errors.
* Probably more reliable detection of pin events in small groups.
* Fixed send methods on `client.conversation()
  <telethon.client.dialogs.DialogMethods.conversation>` were not honoring
  cancellation.
* Flood waits of zero seconds are handled better.
* Getting the pinned message in a chat was failing.
* Fixed the return value when forwarding messages if some were missing
  and also the return value of albums.

Enhancements
~~~~~~~~~~~~

* ``.tgs`` files are now recognised as animated stickers.
* The service message produced by `Message.pin()
  <telethon.tl.custom.message.Message.pin>` is now returned.
* Sending a file with `client.send_file()
  <telethon.client.uploads.UploadMethods.send_file>` now works fine when
  you pass an existing dice media (e.g. sending a message copy).
* `client.edit_permissions() <telethon.client.chats.ChatMethods.edit_permissions>`
  now has the ``embed_links`` parameter which was missing.

Bug Fixes (v1.13)
=================

*Published at 2020/04/25*

+------------------------+
| Scheme layer used: 112 |
+------------------------+

Bug fixes and layer bump.

Bug fixes
~~~~~~~~~

* Passing ``None`` as the entity to `client.delete_messages()
  <telethon.client.messages.MessageMethods.delete_messages>` would fail.
* When downloading a thumbnail, the name inferred was wrong.

Bug Fixes (v1.12)
=================

*Published at 2020/04/20*

+------------------------+
| Scheme layer used: 111 |
+------------------------+

Once again nothing major, but a few bug fixes and primarily the new layer
deserves a new minor release.

Bug fixes
~~~~~~~~~

These were already included in the ``v1.11.3`` patch:

* ``libssl`` check was failing on macOS.
* Getting input users would sometimes fail on `events.ChatAction
  <telethon.events.chataction.ChatAction>`.

These bug fixes are available in this release and beyond:

* Avoid another occurrence of `MemoryError`.
* Sending large files in albums would fail because it tried to cache them.
* The ``thumb`` was being ignored when sending files from :tl:`InputFile`.
* Fixed editing inline messages from callback queries in some cases.
* Proxy connection is now blocking which should help avoid some errors.


Bug Fixes (v1.11)
=================

*Published at 2020/02/20*

+------------------------+
| Scheme layer used: 110 |
+------------------------+

It has been a while since the last release, and a few bug fixes have been
made since then. This release includes them and updates the scheme layer.

Note that most of the bug-fixes are available in the ``v1.10.10`` patch.

Bug fixes
~~~~~~~~~

* Fix ``MemoryError`` when casting certain media.
* Fix `client.get_entity() <telethon.client.users.UserMethods.get_entity>`
  on small group chats.
* `client.delete_dialog() <telethon.client.dialogs.DialogMethods.delete_dialog>`
  now handles deactivated chats more gracefully.
* Sending a message with ``file=`` would ignore some of the parameters.
* Errors are now un-pickle-able once again.
* Fixed some issues regarding markdown and HTML (un)parsing.

The following are also present in ``v1.10.10``:

* Fixed some issues with `events.Album <telethon.events.album.Album>`.
* Fixed some issues with `client.kick_participant()
  <telethon.client.chats.ChatMethods.kick_participant>` and
  `client.edit_admin() <telethon.client.chats.ChatMethods.edit_admin>`.
* Fixed sending albums and more within `client.conversation()
  <telethon.client.dialogs.DialogMethods.conversation>`.
* Fixed some import issues.
* And a lot more minor stuff.

Enhancements
~~~~~~~~~~~~

* Videos can now be included when sending albums.
* Getting updates after reconnect should be more reliable.
* Updated documentation and added more examples.
* More security checks during the generation of the authorization key.

The following are also present in ``v1.10.10``:

* URLs like ``t.me/@username`` are now valid.
* Auto-sleep now works for slow-mode too.
* Improved some error messages.
* Some internal improvements and updating.
* `client.pin_message() <telethon.client.messages.MessageMethods.pin_message>`
  now also works with message objects.
* Asynchronous file descriptors are now allowed during download and upload.


Scheduled Messages (v1.10)
==========================

*Published at 2019/09/08*

+------------------------+
| Scheme layer used: 105 |
+------------------------+

You can now schedule messages to be sent (or edited, or forwarded…) at a later
time, which can also work as reminders for yourself when used in your own chat!

.. code-block:: python

    from datetime import timedelta

    # Remind yourself to walk the dog in 10 minutes (after you play with Telethon's update)
    await client.send_message('me', 'Walk the dog',
                              schedule=timedelta(minutes=10))

    # Remind your friend tomorrow to update Telethon
    await client.send_message(friend, 'Update Telethon!',
                              schedule=timedelta(days=1))

Additions
~~~~~~~~~

* New `Button.auth <telethon.tl.custom.button.Button.auth>` friendly button
  you can use to ask users to login to your bot.
* Telethon's repository now contains ``*.nix`` expressions that you can use.
* New `client.kick_participant() <telethon.client.chats.ChatMethods.kick_participant>`
  method to truly kick (not ban) participants.
* New ``schedule`` parameter in `client.send_message()
  <telethon.client.messages.MessageMethods.send_message>`, `client.edit_message()
  <telethon.client.messages.MessageMethods.edit_message>`, `client.forward_messages()
  <telethon.client.messages.MessageMethods.forward_messages>` and `client.send_file()
  <telethon.client.uploads.UploadMethods.send_file>`.

Bug fixes
~~~~~~~~~

* Fix calling ``flush`` on file objects which lack this attribute.
* Fix `CallbackQuery <telethon.events.callbackquery.CallbackQuery>` pattern.
* Fix `client.action() <telethon.client.chats.ChatMethods.action>` not returning
  itself when used in a context manager (so the ``as`` would be `None`).
* Fix sending :tl:`InputKeyboardButtonUrlAuth` as inline buttons.
* Fix `client.edit_permissions() <telethon.client.chats.ChatMethods.edit_permissions>`
  defaults.
* Fix `Forward <telethon.tl.custom.forward.Forward>` had its ``client`` as `None`.
* Fix (de)serialization of negative timestamps (caused by the information in some
  sites with instant view, where the date could be very old).
* Fix HTML un-parsing.
* Fix ``to/from_id`` in private messages when using multiple clients.
* Stop disconnecting from `None` (incorrect logging).
* Fix double-read on double-connect.
* Fix `client.get_messages() <telethon.client.messages.MessageMethods.get_messages>`
  when being passed more than 100 IDs.
* Fix `Message.document <telethon.tl.custom.message.Message.document>`
  for documents coming from web-pages.

Enhancements
~~~~~~~~~~~~

* Some documentation improvements, including the TL reference.
* Documentation now avoids ``telethon.sync``, which should hopefully be less confusing.
* Better error messages for flood wait.
* You can now `client.get_drafts() <telethon.client.dialogs.DialogMethods.get_drafts>`
  for a single entity (which means you can now get a single draft from a single chat).
* New-style file IDs now work with Telethon.
* The ``progress_callback`` for `client.upload_file()
  <telethon.client.uploads.UploadMethods.upload_file>` can now be an ``async def``.


Animated Stickers (v1.9)
========================

*Published at 2019/07/06*

+------------------------+
| Scheme layer used: 103 |
+------------------------+

With the layer 103, Telethon is now able to send and receive animated
stickers! These use the ``'application/x-tgsticker'`` mime-type and for
now, you can access its raw data, which is a gzipped JSON.


Additions
~~~~~~~~~

* New `events.Album <telethon.events.album.Album>` to easily receive entire albums!
* New `client.edit_admin() <telethon.client.chats.ChatMethods.edit_admin>`
  and `client.edit_permissions() <telethon.client.chats.ChatMethods.edit_permissions>`
  methods to more easily manage your groups.
* New ``pattern=`` in `CallbackQuery
  <telethon.events.callbackquery.CallbackQuery>`.
* New `conversation.cancel_all()
  <telethon.tl.custom.conversation.Conversation.cancel>` method,
  to cancel all currently-active conversations in a particular chat.
* New `telethon.utils.encode_waveform` and `telethon.utils.decode_waveform`
  methods as implemented by Telegram Desktop, which lets you customize how
  voice notes will render.
* New ``ignore_pinned`` parameter in `client.iter_dialogs()
  <telethon.client.dialogs.DialogMethods.iter_dialogs>`.
* New `Message.mark_read() <telethon.tl.custom.message.Message.mark_read>`
  method.
* You can now use strike-through in markdown with ``~~text~~``, and the
  corresponding HTML tags for strike-through, quotes and underlined text.
* You can now nest entities, as in ``**__text__**``.

Bug fixes
~~~~~~~~~

* Fixed downloading contacts.
* Fixed `client.iter_dialogs()
  <telethon.client.dialogs.DialogMethods.iter_dialogs>` missing some under
  certain circumstances.
* Fixed incredibly slow imports under some systems due to expensive path
  resolution when searching for ``libssl``.
* Fixed captions when sending albums.
* Fixed invalid states in `Conversation
  <telethon.tl.custom.conversation.Conversation>`.
* Fixes to some methods in utils regarding extensions.
* Fixed memory cycle in `Forward <telethon.tl.custom.forward.Forward>`
  which let you do things like the following:

  .. code-block:: python

      original_fwd = message.forward.original_fwd.original_fwd.original_fwd.original_fwd.original_fwd.original_fwd

  Hopefully you didn't rely on that in your code.
* Fixed `File.ext <telethon.tl.custom.file.File.ext>` not working on
  unknown mime-types, despite the file name having the extension.
* Fixed ``ids=..., reverse=True`` in `client.iter_messages()
  <telethon.client.messages.MessageMethods.iter_messages>`.
* Fixed `Draft <telethon.tl.custom.draft.Draft>` not being aware
  of the entity.
* Added missing re-exports in ``telethon.sync``.

Enhancements
~~~~~~~~~~~~

* Improved `conversation.cancel()
  <telethon.tl.custom.conversation.Conversation.cancel>`
  behaviour. Now you can use it from anywhere.
* The ``progress_callback`` in `client.download_media()
  <telethon.client.downloads.DownloadMethods.download_media>`
  now lets you use ``async def``.
* Improved documentation and the online
  method reference at https://tl.telethon.dev.


Documentation Overhaul (v1.8)
=============================

*Published at 2019/05/30*

+------------------------+
| Scheme layer used: 100 |
+------------------------+

The documentation has been completely reworked from the ground up,
with awesome new quick references such as :ref:`client-ref` to help
you quickly find what you need!

Raw methods also warn you when a friendly variant is available, so
that you don't accidentally make your life harder than it has to be.

In addition, all methods in the client now are fully annotated with type
hints! More work needs to be done, but this should already help a lot when
using Telethon from any IDEs.

You may have noticed that the patch versions between ``v1.7.2`` to ``v1.7.7``
have not been documented. This is because patch versions should only contain
bug fixes, no new features or breaking changes. This hasn't been the case in
the past, but from now on, the library will try to adhere more strictly to
the `Semantic Versioning <https://semver.org>`_ principles.

If you ever want to look at those bug fixes, please use the appropriated
``git`` command, such as ``git shortlog v1.7.1...v1.7.4``, but in general,
they probably just fixed your issue.

With that out of the way, let's look at the full change set:


Breaking Changes
~~~~~~~~~~~~~~~~

* The layer changed, so take note if you use the raw API, as it's usual.
* The way photos are downloaded changed during the layer update of the
  previous version, and fixing that bug as a breaking change in itself.
  `client.download_media() <telethon.client.downloads.DownloadMethods.download_media>`
  now offers a different way to deal with thumbnails.


Additions
~~~~~~~~~

* New `Message.file <telethon.tl.custom.message.Message.file>` property!
  Now you can trivially access `message.file.id  <telethon.tl.custom.file.File.id>`
  to get the file ID of some media, or even ``print(message.file.name)``.
* Archiving dialogs with `Dialog.archive() <telethon.tl.custom.dialog.Dialog.archive>`
  or `client.edit_folder() <telethon.client.dialogs.DialogMethods.edit_folder>`
  is now possible.
* New cleaned-up method to stream downloads with `client.iter_download()
  <telethon.client.downloads.DownloadMethods.iter_download>`, which offers
  a lot of flexibility, such as arbitrary offsets for efficient seeking.
* `Dialog.delete() <telethon.tl.custom.dialog.Dialog.delete>` has existed
  for a while, and now `client.delete_dialog()
  <telethon.client.dialogs.DialogMethods.delete_dialog>` exists too so you
  can easily leave chats or delete dialogs without fetching all dialogs.
* Some people or chats have a lot of profile photos. You can now iterate
  over all of them with the new `client.iter_profile_photos()
  <telethon.client.chats.ChatMethods.iter_profile_photos>` method.
* You can now annoy everyone with the new `Message.pin(notify=True)
  <telethon.tl.custom.message.Message.pin>`! The client has its own
  variant too, called `client.pin_message()
  <telethon.client.messages.MessageMethods.pin_message>`.


Bug fixes
~~~~~~~~~

* Correctly catch and raise all RPC errors.
* Downloading stripped photos wouldn't work correctly.
* Under some systems, ``libssl`` would fail to load earlier than
  expected, causing the library to fail when being imported.
* `conv.get_response() <telethon.tl.custom.conversation.Conversation.get_response>`
  after ID 0 wasn't allowed when it should.
* `InlineBuilder <telethon.tl.custom.inlinebuilder.InlineBuilder>` only worked
  with local files, but files from anywhere are supported.
* Accessing the text property from a raw-API call to fetch :tl:`Message` would fail
  (any any other property that needed the client).
* Database is now upgraded if the version was lower, not different.
  From now on, this should help with upgrades and downgrades slightly.
* Fixed saving ``pts`` and session-related stuff.
* Disconnection should not raise any errors.
* Invite links of the form ``tg://join?invite=`` now work.
* `client.iter_participants(search=...) <telethon.client.chats.ChatMethods.iter_participants>`
  now works on private chats again.
* Iterating over messages in reverse with a date as offset wouldn't work.
* The conversation would behave weirdly when a timeout occurred.


Enhancements
~~~~~~~~~~~~

* ``telethon`` now re-export all the goodies that you commonly need when
  using the library, so e.g. ``from telethon import Button`` will now work.
* ``telethon.sync`` now re-exports everything from ``telethon``, so that
  you can trivially import from just one place everything that you need.
* More attempts at reducing CPU usage after automatically fetching missing
  entities on events. This isn't a big deal, even if it sounds like one.
* Hexadecimal invite links are now supported. You didn't need them, but
  they will now work.

Internal Changes
~~~~~~~~~~~~~~~~

* Deterministic code generation. This is good for ``diff``.
* On Python 3.7 and above, we properly close the connection.
* A lot of micro-optimization.
* Fixes to bugs introduced while making this release.
* Custom commands on ``setup.py`` are nicer to use.



Fix-up for Photo Downloads (v1.7.1)
===================================

*Published at 2019/04/24*

Telegram changed the way thumbnails (which includes photos) are downloaded,
so you can no longer use a :tl:`PhotoSize` alone to download a particular
thumbnail size (this is a **breaking change**).

Instead, you will have to specify the new ``thumb`` parameter in
`client.download_media() <telethon.client.downloads.DownloadMethods.download_media>`
to download a particular thumbnail size. This addition enables you to easily
download thumbnails from documents, something you couldn't do easily before.


Easier Events (v1.7)
====================

*Published at 2019/04/22*

+-----------------------+
| Scheme layer used: 98 |
+-----------------------+

If you have been using Telethon for a while, you probably know how annoying
the "Could not find the input entity for…" error can be. In this new version,
the library will try harder to find the input entity for you!

That is, instead of doing:

.. code-block:: python

    @client.on(events.NewMessage)
    async def handler(event):
        await client.download_profile_photo(await event.get_input_sender())
        # ...... needs await, it's a method ^^^^^                       ^^

You can now do:

.. code-block:: python

    @client.on(events.NewMessage)
    async def handler(event):
        await client.download_profile_photo(event.input_sender)
        # ...... no await, it's a property! ^
        # It's also 12 characters shorter :)

And even the following will hopefully work:

.. code-block:: python

    @client.on(events.NewMessage)
    async def handler(event):
        await client.download_profile_photo(event.sender_id)

A lot of people use IDs thinking this is the right way of doing it. Ideally,
you would always use ``input_*``, not ``sender`` or ``sender_id`` (and the
same applies to chats). But, with this change, IDs will work just the same as
``input_*`` inside events.

**This feature still needs some more testing**, so please do open an issue
if you find strange behaviour.


Breaking Changes
~~~~~~~~~~~~~~~~

* The layer changed, and a lot of things did too. If you are using
  raw API, you should be careful with this. In addition, some attributes
  weren't of type ``datetime`` when they should be, which has been fixed.
* Due to the layer change, you can no longer download photos with just
  their :tl:`PhotoSize`. Version 1.7.1 introduces a new way to download
  thumbnails to work around this issue.
* `client.disconnect()
  <telethon.client.telegrambaseclient.TelegramBaseClient.disconnect>`
  is now asynchronous again. This means you need to ``await`` it. You
  don't need to worry about this if you were using ``with client`` or
  `client.run_until_disconnected
  <telethon.client.updates.UpdateMethods.run_until_disconnected>`.
  This should prevent the "pending task was destroyed" errors.

Additions
~~~~~~~~~

* New in-memory cache for input entities. This should mean a lot less
  of disk look-ups.
* New `client.action <telethon.client.chats.ChatMethods.action>` method
  to easily indicate that you are doing some chat action:

  .. code-block:: python

        async with client.action(chat, 'typing'):
            await asyncio.sleep(2)  # type for 2 seconds
            await client.send_message(chat, 'Hello world! I type slow ^^')

  You can also easily use this for sending files, playing games, etc.


New bugs
~~~~~~~~

* Downloading photos is broken. This is fixed in v1.7.1.

Bug fixes
~~~~~~~~~

* Fix sending photos from streams/bytes.
* Fix unhandled error when sending requests that were too big.
* Fix edits that arrive too early on conversations.
* Fix `client.edit_message()
  <telethon.client.messages.MessageMethods.edit_message>`
  when trying to edit a file.
* Fix method calls on the objects returned by `client.iter_dialogs()
  <telethon.client.dialogs.DialogMethods.iter_dialogs>`.
* Attempt at fixing `client.iter_dialogs()
  <telethon.client.dialogs.DialogMethods.iter_dialogs>` missing many dialogs.
* ``offset_date`` in `client.iter_messages()
  <telethon.client.messages.MessageMethods.iter_messages>` was being
  ignored in some cases. This has been worked around.
* Fix `callback_query.edit()
  <telethon.events.callbackquery.CallbackQuery.Event.edit>`.
* Fix `CallbackQuery(func=...) <telethon.events.callbackquery.CallbackQuery>`
  was being ignored.
* Fix `UserUpdate <telethon.events.userupdate.UserUpdate>` not working for
  "typing" (and uploading file, etc.) status.
* Fix library was not expecting ``IOError`` from PySocks.
* Fix library was raising a generic ``ConnectionError``
  and not the one that actually occurred.
* Fix the ``blacklist_chats`` parameter in `MessageRead
  <telethon.events.messageread.MessageRead>` not working as intended.
* Fix `client.download_media(contact)
  <telethon.client.downloads.DownloadMethods.download_media>`.
* Fix mime type when sending ``mp3`` files.
* Fix forcibly getting the sender or chat from events would
  not always return all their information.
* Fix sending albums with `client.send_file()
  <telethon.client.uploads.UploadMethods.send_file>` was not returning
  the sent messages.
* Fix forwarding albums with `client.forward_messages()
  <telethon.client.messages.MessageMethods.forward_messages>`.
* Some fixes regarding filtering updates from chats.
* Attempt at preventing duplicated updates.
* Prevent double auto-reconnect.


Enhancements
~~~~~~~~~~~~

* Some improvements related to proxy connections.
* Several updates and improvements to the documentation,
  such as optional dependencies now being properly listed.
* You can now forward messages from different chats directly with
  `client.forward_messages <telethon.client.messages.MessageMethods.forward_messages>`.


Tidying up Internals (v1.6)
===========================

*Published at 2019/02/27*

+-----------------------+
| Scheme layer used: 95 |
+-----------------------+

First things first, sorry for updating the layer in the previous patch
version. That should only be done between major versions ideally, but
due to how Telegram works, it's done between minor versions. However raw
API has and will always be considered "unsafe", this meaning that you
should always use the convenience client methods instead. These methods
don't cover the full API yet, so pull requests are welcome.

Breaking Changes
~~~~~~~~~~~~~~~~

* The layer update, of course. This didn't really need a mention here.
* You can no longer pass a ``batch_size`` when iterating over messages.
  No other method exposed this parameter, and it was only meant for testing
  purposes. Instead, it's now a private constant.
* ``client.iter_*`` methods no longer have a ``_total`` parameter which
  was supposed to be private anyway. Instead, they return a new generator
  object which has a ``.total`` attribute:

  .. code-block:: python

      it = client.iter_messages(chat)
      for i, message in enumerate(it, start=1):
          percentage = i / it.total
          print('{:.2%} {}'.format(percentage, message.text))

Additions
~~~~~~~~~

* You can now pass ``phone`` and ``phone_code_hash`` in `client.sign_up
  <telethon.client.auth.AuthMethods.sign_up>`, although you probably don't
  need that.
* Thanks to the overhaul of all ``client.iter_*`` methods, you can now do:

  .. code-block:: python

      for message in reversed(client.iter_messages('me')):
          print(message.text)

Bug fixes
~~~~~~~~~

* Fix `telethon.utils.resolve_bot_file_id`, which wasn't working after
  the layer update (so you couldn't send some files by bot file IDs).
* Fix sending albums as bot file IDs (due to image detection improvements).
* Fix `takeout() <telethon.client.account.AccountMethods.takeout>` failing
  when they need to download media from other DCs.
* Fix repeatedly calling `conversation.get_response()
  <telethon.tl.custom.conversation.Conversation.get_response>` when many
  messages arrived at once (i.e. when several of them were forwarded).
* Fixed connecting with `ConnectionTcpObfuscated
  <telethon.network.connection.tcpobfuscated.ConnectionTcpObfuscated>`.
* Fix `client.get_peer_id('me')
  <telethon.client.users.UserMethods.get_peer_id>`.
* Fix warning of "missing sqlite3" when in reality it just had wrong tables.
* Fix a strange error when using too many IDs in `client.delete_messages()
  <telethon.client.messages.MessageMethods.delete_messages>`.
* Fix `client.send_file <telethon.client.uploads.UploadMethods.send_file>`
  with the result of `client.upload_file
  <telethon.client.uploads.UploadMethods.upload_file>`.
* When answering inline results, their order was not being preserved.
* Fix `events.ChatAction <telethon.events.chataction.ChatAction>`
  detecting user leaves as if they were kicked.

Enhancements
~~~~~~~~~~~~

* Cleared up some parts of the documentation.
* Improved some auto-casts to make life easier.
* Improved image detection. Now you can easily send `bytes`
  and streams of images as photos, unless you force document.
* Sending images as photos that are too large will now be resized
  before uploading, reducing the time it takes to upload them and
  also avoiding errors when the image was too large (as long as
  ``pillow`` is installed). The images will remain unchanged if you
  send it as a document.
* Treat ``errors.RpcMcgetFailError`` as a temporary server error
  to automatically retry shortly. This works around most issues.

Internal changes
~~~~~~~~~~~~~~~~

* New common way to deal with retries (``retry_range``).
* Cleaned up the takeout client.
* Completely overhauled asynchronous generators.

Layer Update (v1.5.5)
=====================

*Published at 2019/01/14*

+-----------------------+
| Scheme layer used: 93 |
+-----------------------+

There isn't an entry for v1.5.4 because it contained only one hot-fix
regarding loggers. This update is slightly bigger so it deserves mention.

Additions
~~~~~~~~~

* New ``supports_streaming`` parameter in `client.send_file
  <telethon.client.uploads.UploadMethods.send_file>`.

Bug fixes
~~~~~~~~~

* Dealing with mimetypes should cause less issues in systems like Windows.
* Potentially fix alternative session storages that had issues with dates.

Enhancements
~~~~~~~~~~~~

* Saner timeout defaults for conversations.
* ``Path``-like files are now supported for thumbnails.
* Added new hot-keys to the online documentation at
  https://tl.telethon.dev/ such as ``/`` to search.
  Press ``?`` to view them all.


Bug Fixes (v1.5.3)
==================

*Published at 2019/01/14*

Several bug fixes and some quality of life enhancements.

Breaking Changes
~~~~~~~~~~~~~~~~

* `message.edit <telethon.tl.custom.message.Message.edit>` now respects
  the previous message buttons or link preview being hidden. If you want to
  toggle them you need to explicitly set them. This is generally the desired
  behaviour, but may cause some bots to have buttons when they shouldn't.

Additions
~~~~~~~~~

* You can now "hide_via" when clicking on results from `client.inline_query
  <telethon.client.bots.BotMethods.inline_query>` to @bing and @gif.
* You can now further configure the logger Telethon uses to suit your needs.

Bug fixes
~~~~~~~~~

* Fixes for ReadTheDocs to correctly build the documentation.
* Fix :tl:`UserEmpty` not being expected when getting the input variant.
* The message object returned when sending a message with buttons wouldn't
  always contain the :tl:`ReplyMarkup`.
* Setting email when configuring 2FA wasn't properly supported.
* ``utils.resolve_bot_file_id`` now works again for photos.

Enhancements
~~~~~~~~~~~~

* Chat and channel participants can now be used as peers.
* Reworked README and examples at
  https://github.com/LonamiWebs/Telethon/tree/master/telethon_examples


Takeout Sessions (v1.5.2)
=========================

*Published at 2019/01/05*

You can now easily start takeout sessions (also known as data export sessions)
through `client.takeout() <telethon.client.account.AccountMethods.takeout>`.
Some of the requests will have lower flood limits when done through the
takeout session.

Bug fixes
~~~~~~~~~

* The new `AdminLogEvent <telethon.tl.custom.adminlogevent.AdminLogEvent>`
  had a bug that made it unusable.
* `client.iter_dialogs() <telethon.client.dialogs.DialogMethods.iter_dialogs>`
  will now locally check for the offset date, since Telegram ignores it.
* Answering inline queries with media no works properly. You can now use
  the library to create inline bots and send stickers through them!


object.to_json() (v1.5.1)
=========================

*Published at 2019/01/03*

The library already had a way to easily convert the objects the API returned
into dictionaries through ``object.to_dict()``, but some of the fields are
dates or `bytes` which JSON can't serialize directly.

For convenience, a new ``object.to_json()`` has been added which will by
default format both of those problematic types into something sensible.

Additions
~~~~~~~~~

* New `client.iter_admin_log()
  <telethon.client.chats.ChatMethods.iter_admin_log>` method.

Bug fixes
~~~~~~~~~

* `client.is_connected()
  <telethon.client.telegrambaseclient.TelegramBaseClient.is_connected>`
  would be wrong when the initial connection failed.
* Fixed ``UnicodeDecodeError`` when accessing the text of messages
  with malformed offsets in their entities.
* Fixed `client.get_input_entity()
  <telethon.client.users.UserMethods.get_input_entity>` for integer IDs
  that the client has not seen before.

Enhancements
~~~~~~~~~~~~

* You can now configure the reply markup when using `Button
  <telethon.tl.custom.button.Button>` as a bot.
* More properties for `Message
  <telethon.tl.custom.message.Message>` to make accessing media convenient.
* Downloading to ``file=bytes`` will now return a `bytes` object
  with the downloaded media.


Polls with the Latest Layer (v1.5)
==================================

*Published at 2018/12/25*

+-----------------------+
| Scheme layer used: 91 |
+-----------------------+

This version doesn't really bring many new features, but rather focuses on
updating the code base to support the latest available Telegram layer, 91.
This layer brings polls, and you can create and manage them through Telethon!

Breaking Changes
~~~~~~~~~~~~~~~~

* The layer change from 82 to 91 changed a lot of things in the raw API,
  so be aware that if you rely on raw API calls, you may need to update
  your code, in particular **if you work with files**. They have a new
  ``file_reference`` parameter that you must provide.

Additions
~~~~~~~~~

* New `client.is_bot() <telethon.client.users.UserMethods.is_bot>` method.

Bug fixes
~~~~~~~~~

* Markdown and HTML parsing now behave correctly with leading whitespace.
* HTTP connection should now work correctly again.
* Using ``caption=None`` would raise an error instead of setting no caption.
* ``KeyError`` is now handled properly when forwarding messages.
* `button.click() <telethon.tl.custom.messagebutton.MessageButton.click>`
  now works as expected for :tl:`KeyboardButtonGame`.

Enhancements
~~~~~~~~~~~~

* Some improvements to the search in the full API and generated examples.
* Using entities with ``access_hash = 0`` will now work in more cases.

Internal changes
~~~~~~~~~~~~~~~~

* Some changes to the documentation and code generation.
* 2FA code was updated to work under the latest layer.


Error Descriptions in CSV files (v1.4.3)
========================================

*Published at 2018/12/04*

While this may seem like a minor thing, it's a big usability improvement.

Anyone who wants to update the documentation for known errors, or whether
some methods can be used as a bot, user or both, can now be easily edited.
Everyone is encouraged to help document this better!

Bug fixes
~~~~~~~~~

* ``TimeoutError`` was not handled during automatic reconnects.
* Getting messages by ID using :tl:`InputMessageReplyTo` could fail.
* Fixed `message.get_reply_message
  <telethon.tl.custom.message.Message.get_reply_message>`
  as a bot when a user replied to a different bot.
* Accessing some document properties in a `Message
  <telethon.tl.custom.message.Message>` would fail.

Enhancements
~~~~~~~~~~~~

* Accessing `events.ChatAction <telethon.events.chataction.ChatAction>`
  properties such as input users may now work in more cases.

Internal changes
~~~~~~~~~~~~~~~~

* Error descriptions and information about methods is now loaded
  from a CSV file instead of being part of several messy JSON files.


Bug Fixes (v1.4.2)
==================

*Published at 2018/11/24*

This version also includes the v1.4.1 hot-fix, which was a single
quick fix and didn't really deserve an entry in the changelog.

Bug fixes
~~~~~~~~~

* Authorization key wouldn't be saved correctly, requiring re-login.
* Conversations with custom events failed to be cancelled.
* Fixed ``telethon.sync`` when using other threads.
* Fix markdown/HTML parser from failing with leading/trailing whitespace.
* Fix accessing ``chat_action_event.input_user`` property.
* Potentially improved handling unexpected disconnections.


Enhancements
~~~~~~~~~~~~

* Better default behaviour for `client.send_read_acknowledge
  <telethon.client.messages.MessageMethods.send_read_acknowledge>`.
* Clarified some points in the documentation.
* Clearer errors for ``utils.get_peer*``.


Connection Overhaul (v1.4)
==========================

*Published at 2018/11/03*

Yet again, a lot of work has been put into reworking the low level connection
classes. This means ``asyncio.open_connection`` is now used correctly and the
errors it can produce are handled properly. The separation between packing,
encrypting and network is now abstracted away properly, so reasoning about
the code is easier, making it more maintainable.

As a user, you shouldn't worry about this, other than being aware that quite
a few changes were made in the insides of the library and you should report
any issues that you encounter with this version if any.


Breaking Changes
~~~~~~~~~~~~~~~~

* The threaded version of the library will no longer be maintained, primarily
  because it never was properly maintained anyway. If you have old code, stick
  with old versions of the library, such as ``0.19.1.6``.
* Timeouts no longer accept ``timedelta``. Simply use seconds.
* The ``callback`` parameter from `telethon.tl.custom.button.Button.inline()`
  was removed, since it had always been a bad idea. Adding the callback there
  meant a lot of extra work for every message sent, and only registering it
  after the first message was sent! Instead, use
  `telethon.events.callbackquery.CallbackQuery`.


Additions
~~~~~~~~~

* New `dialog.delete() <telethon.tl.custom.dialog.Dialog.delete>` method.
* New `conversation.cancel()
  <telethon.tl.custom.conversation.Conversation.cancel>` method.
* New ``retry_delay`` delay for the client to be used on auto-reconnection.


Bug fixes
~~~~~~~~~

* Fixed `Conversation.wait_event()
  <telethon.tl.custom.conversation.Conversation.wait_event>`.
* Fixed replying with photos/documents on inline results.
* `client.is_user_authorized()
  <telethon.client.users.UserMethods.is_user_authorized>` now works
  correctly after `client.log_out()
  <telethon.client.auth.AuthMethods.log_out>`.
* `dialog.is_group <telethon.tl.custom.dialog.Dialog>` now works for
  :tl:`ChatForbidden`.
* Not using ``async with`` when needed is now a proper error.
* `events.CallbackQuery <telethon.events.callbackquery.CallbackQuery>`
  with string regex was not working properly.
* `client.get_entity('me') <telethon.client.users.UserMethods.get_entity>`
  now works again.
* Empty codes when signing in are no longer valid.
* Fixed file cache for in-memory sessions.


Enhancements
~~~~~~~~~~~~

* Support ``next_offset`` in `inline_query.answer()
  <telethon.events.inlinequery.InlineQuery.Event.answer>`.
* Support ``<a href="tg://user?id=123">`` mentions in HTML parse mode.
* New auto-casts for :tl:`InputDocument` and :tl:`InputChatPhoto`.
* Conversations are now exclusive per-chat by default.
* The request that caused a RPC error is now shown in the error message.
* New full API examples in the generated documentation.
* Fixed some broken links in the documentation.
* `client.disconnect()
  <telethon.client.telegrambaseclient.TelegramBaseClient.disconnect>`
  is now synchronous, but you can still ``await`` it for consistency
  or compatibility.


Event Templates (v1.3)
======================

*Published at 2018/09/22*


If you have worked with Flask templates, you will love this update,
since it gives you the same features but even more conveniently:

.. code-block:: python

    # handlers/welcome.py
    from telethon import events

    @events.register(events.NewMessage('(?i)hello'))
    async def handler(event):
        client = event.client
        await event.respond('Hi!')
        await client.send_message('me', 'Sent hello to someone')


This will `register <telethon.events.register>` the ``handler`` callback
to handle new message events. Note that you didn't add this to any client
yet, and this is the key point: you don't need a client to define handlers!
You can add it later:

.. code-block:: python

    # main.py
    from telethon import TelegramClient
    import handlers.welcome

    with TelegramClient(...) as client:
        # This line adds the handler we defined before for new messages
        client.add_event_handler(handlers.welcome.handler)
        client.run_until_disconnected()


This should help you to split your big code base into a more modular design.


Breaking Changes
~~~~~~~~~~~~~~~~

* ``.sender`` is the ``.chat`` when the message is sent in a broadcast
  channel. This makes sense, because the sender of the message was the
  channel itself, but you now must take into consideration that it may
  be either a :tl:`User` or :tl:`Channel` instead of being `None`.


Additions
~~~~~~~~~

* New ``MultiError`` class when invoking many requests at once
  through ``client([requests])``.
* New custom ``func=`` on all events. These will receive the entire
  event, and a good usage example is ``func=lambda e: e.is_private``.
* New ``.web_preview`` field on messages. The ``.photo`` and ``.document``
  will also return the media in the web preview if any, for convenience.
* Callback queries now have a ``.chat`` in most circumstances.


Bug fixes
~~~~~~~~~

* Running code with `python3 -O` would remove critical code from asserts.
* Fix some rare ghost disconnections after reconnecting.
* Fix strange behavior for `send_message(chat, Message, reply_to=foo)
  <telethon.client.messages.MessageMethods.send_message>`.
* The ``loop=`` argument was being pretty much ignored.
* Fix ``MemorySession`` file caching.
* The logic for getting entities from their username is now correct.
* Fixes for sending stickers from ``.webp`` files in Windows, again.
* Fix disconnection without being logged in.
* Retrieving media from messages would fail.
* Getting some messages by ID on private chats.


Enhancements
~~~~~~~~~~~~

* `iter_participants <telethon.client.chats.ChatMethods.iter_participants>`
  will now use its ``search=`` as a symbol set when ``aggressive=True``,
  so you can do ``client.get_participants(group, aggressive=True,
  search='абвгдеёжзийклмнопрст')``.
* The ``StringSession`` supports custom encoding.
* Callbacks for `telethon.client.auth.AuthMethods.start` can be ``async``.


Internal changes
~~~~~~~~~~~~~~~~

* Cherry-picked a commit to use ``asyncio.open_connection`` in the lowest
  level of the library. Do open issues if this causes trouble, but it should
  otherwise improve performance and reliability.
* Building and resolving events overhaul.


Conversations, String Sessions and More (v1.2)
==============================================

*Published at 2018/08/14*


This is a big release! Quite a few things have been added to the library,
such as the new `Conversation <telethon.tl.custom.conversation.Conversation>`.
This makes it trivial to get tokens from `@BotFather <https://t.me/BotFather>`_:

.. code-block:: python

    from telethon.tl import types

    with client.conversation('BotFather') as conv:
        conv.send_message('/mybots')
        message = conv.get_response()
        message.click(0)
        message = conv.get_edit()
        message.click(0)
        message = conv.get_edit()
        for _, token in message.get_entities_text(types.MessageEntityCode):
            print(token)


In addition to that, you can now easily load and export session files
without creating any on-disk file thanks to the ``StringSession``:

.. code-block:: python

    from telethon.sessions import StringSession
    string = StringSession.save(client.session)

Check out :ref:`sessions` for more details.

For those who aren't able to install ``cryptg``, the support for ``libssl``
has been added back. While interfacing ``libssl`` is not as fast, the speed
when downloading and sending files should really be noticeably faster.

While those are the biggest things, there are still more things to be
excited about.


Additions
~~~~~~~~~

- The mentioned method to start a new `client.conversation
  <telethon.client.dialogs.DialogMethods.conversation>`.
- Implemented global search through `client.iter_messages
  <telethon.client.messages.MessageMethods.iter_messages>`
  with `None` entity.
- New `client.inline_query <telethon.client.bots.BotMethods.inline_query>`
  method to perform inline queries.
- Bot-API-style ``file_id`` can now be used to send files and download media.
  You can also access `telethon.utils.resolve_bot_file_id` and
  `telethon.utils.pack_bot_file_id` to resolve and create these
  file IDs yourself. Note that each user has its own ID for each file
  so you can't use a bot's ``file_id`` with your user, except stickers.
- New `telethon.utils.get_peer`, useful when you expect a :tl:`Peer`.

Bug fixes
~~~~~~~~~

- UTC timezone for `telethon.events.userupdate.UserUpdate`.
- Bug with certain input parameters when iterating messages.
- RPC errors without parent requests caused a crash, and better logging.
- ``incoming = outgoing = True`` was not working properly.
- Getting a message's ID was not working.
- File attributes not being inferred for ``open()``'ed files.
- Use ``MemorySession`` if ``sqlite3`` is not installed by default.
- Self-user would not be saved to the session file after signing in.
- `client.catch_up() <telethon.client.updates.UpdateMethods.catch_up>`
  seems to be functional again.


Enhancements
~~~~~~~~~~~~

- Updated documentation.
- Invite links will now use cache, so using them as entities is cheaper.
- You can reuse message buttons to send new messages with those buttons.
- ``.to_dict()`` will now work even on invalid ``TLObject``'s.


Better Custom Message (v1.1.1)
==============================

*Published at 2018/07/23*

The `custom.Message <telethon.tl.custom.message.Message>` class has been
rewritten in a cleaner way and overall feels less hacky in the library.
This should perform better than the previous way in which it was patched.

The release is primarily intended to test this big change, but also fixes
**Python 3.5.2 compatibility** which was broken due to a trailing comma.


Bug fixes
~~~~~~~~~

- Using ``functools.partial`` on event handlers broke updates
  if they had uncaught exceptions.
- A bug under some session files where the sender would export
  authorization for the same data center, which is unsupported.
- Some logical bugs in the custom message class.


Bot Friendly (v1.1)
===================

*Published at 2018/07/21*

Two new event handlers to ease creating normal bots with the library,
namely `events.InlineQuery <telethon.events.inlinequery.InlineQuery>`
and `events.CallbackQuery <telethon.events.callbackquery.CallbackQuery>`
for handling ``@InlineBot queries`` or reacting to a button click. For
this second option, there is an even better way:

.. code-block:: python

    from telethon.tl.custom import Button

    async def callback(event):
        await event.edit('Thank you!')

    bot.send_message(chat, 'Hello!',
                     buttons=Button.inline('Click me', callback))


You can directly pass the callback when creating the button.

This is fine for small bots but it will add the callback every time
you send a message, so you probably should do this instead once you
are done testing:

.. code-block:: python

    markup = bot.build_reply_markup(Button.inline('Click me', callback))
    bot.send_message(chat, 'Hello!', buttons=markup)


And yes, you can create more complex button layouts with lists:

.. code-block:: python

    from telethon import events

    global phone = ''

    @bot.on(events.CallbackQuery)
    async def handler(event):
        global phone
        if event.data == b'<':
            phone = phone[:-1]
        else:
            phone += event.data.decode('utf-8')

        await event.answer('Phone is now {}'.format(phone))

    markup = bot.build_reply_markup([
        [Button.inline('1'), Button.inline('2'), Button.inline('3')],
        [Button.inline('4'), Button.inline('5'), Button.inline('6')],
        [Button.inline('7'), Button.inline('8'), Button.inline('9')],
        [Button.inline('+'), Button.inline('0'), Button.inline('<')],
    ])
    bot.send_message(chat, 'Enter a phone', buttons=markup)


(Yes, there are better ways to do this). Now for the rest of things:


Additions
~~~~~~~~~

- New `custom.Button <telethon.tl.custom.button.Button>` class
  to help you create inline (or normal) reply keyboards. You
  must sign in as a bot to use the ``buttons=`` parameters.
- New events usable if you sign in as a bot: `events.InlineQuery
  <telethon.events.inlinequery.InlineQuery>` and `events.CallbackQuery
  <telethon.events.callbackquery.CallbackQuery>`.
- New ``silent`` parameter when sending messages, usable in broadcast channels.
- Documentation now has an entire section dedicate to how to use
  the client's friendly methods at *(removed broken link)*.

Bug fixes
~~~~~~~~~

- Empty ``except`` are no longer used which means
  sending a keyboard interrupt should now work properly.
- The ``pts`` of incoming updates could be `None`.
- UTC timezone information is properly set for read ``datetime``.
- Some infinite recursion bugs in the custom message class.
- :tl:`Updates` was being dispatched to raw handlers when it shouldn't.
- Using proxies and HTTPS connection mode may now work properly.
- Less flood waits when downloading media from different data centers,
  and the library will now detect them even before sending requests.

Enhancements
~~~~~~~~~~~~

- Interactive sign in now supports signing in with a bot token.
- ``timedelta`` is now supported where a date is expected, which
  means you can e.g. ban someone for ``timedelta(minutes=5)``.
- Events are only built once and reused many times, which should
  save quite a few CPU cycles if you have a lot of the same type.
- You can now click inline buttons directly if you know their data.

Internal changes
~~~~~~~~~~~~~~~~

- When downloading media, the right sender is directly
  used without previously triggering migrate errors.
- Code reusing for getting the chat and the sender,
  which easily enables this feature for new types.


New HTTP(S) Connection Mode (v1.0.4)
====================================

*Published at 2018/07/09*

This release implements the HTTP connection mode to the library, which
means certain proxies that only allow HTTP connections should now work
properly. You can use it doing the following, like any other mode:

.. code-block:: python

    from telethon import TelegramClient, sync
    from telethon.network import ConnectionHttp

    client = TelegramClient(..., connection=ConnectionHttp)
    with client:
        client.send_message('me', 'Hi!')


Additions
~~~~~~~~~

- ``add_mark=`` is now back on ``utils.get_input_peer`` and also on
  `client.get_input_entity() <telethon.client.users.UserMethods.get_input_entity>`.
- New `client.get_peer_id <telethon.client.users.UserMethods.get_peer_id>`
  convenience for ``utils.get_peer_id(await client.get_input_entity(peer))``.


Bug fixes
~~~~~~~~~

- If several `TLMessage` in a `MessageContainer` exceeds 1MB, it will no
  longer be automatically turned into one. This basically means that e.g.
  uploading 10 file parts at once will work properly again.
- Documentation fixes and some missing ``await``.
- Revert named argument for `client.forward_messages
  <telethon.client.messages.MessageMethods.forward_messages>`

Enhancements
~~~~~~~~~~~~

- New auto-casts to :tl:`InputNotifyPeer` and ``chat_id``.

Internal changes
~~~~~~~~~~~~~~~~

- Outgoing `TLMessage` are now pre-packed so if there's an error when
  serializing the raw requests, the library will no longer swallow it.
  This also means re-sending packets doesn't need to re-pack their bytes.



Iterate Messages in Reverse (v1.0.3)
====================================

*Published at 2018/07/04*

+-----------------------+
| Scheme layer used: 82 |
+-----------------------+

Mostly bug fixes, but now there is a new parameter on `client.iter_messages
<telethon.client.messages.MessageMethods.iter_messages>` to support reversing
the order in which messages are returned.

Additions
~~~~~~~~~

- The mentioned ``reverse`` parameter when iterating over messages.
- A new ``sequential_updates`` parameter when creating the client
  for updates to be processed sequentially. This is useful when you
  need to make sure that all updates are processed in order, such
  as a script that only forwards incoming messages somewhere else.

Bug fixes
~~~~~~~~~

- Count was always `None` for `message.button_count
  <telethon.tl.custom.message.Message.button_count>`.
- Some fixes when disconnecting upon dropping the client.
- Support for Python 3.4 in the sync version, and fix media download.
- Some issues with events when accessing the input chat or their media.
- Hachoir wouldn't automatically close the file after reading its metadata.
- Signing in required a named ``code=`` parameter, but usage
  without a name was really widespread so it has been reverted.


Bug Fixes (v1.0.2)
==================

*Published at 2018/06/28*

Updated some asserts and parallel downloads, as well as some fixes for sync.


Bug Fixes (v1.0.1)
==================

*Published at 2018/06/27*

And as usual, every major release has a few bugs that make the library
unusable! This quick update should fix those, namely:

Bug fixes
~~~~~~~~~

- `client.start() <telethon.client.auth.AuthMethods.start>` was completely
  broken due to a last-time change requiring named arguments everywhere.
- Since the rewrite, if your system clock was wrong, the connection would
  get stuck in an infinite "bad message" loop of responses from Telegram.
- Accessing the buttons of a custom message wouldn't work in channels,
  which lead to fix a completely different bug regarding starting bots.
- Disconnecting could complain if the magic ``telethon.sync`` was imported.
- Successful automatic reconnections now ask Telegram to send updates to us
  once again as soon as the library is ready to listen for them.


Synchronous magic (v1.0)
========================

*Published at 2018/06/27*

.. important::

    If you come from Telethon pre-1.0 you **really** want to read
    :ref:`compatibility-and-convenience` to port your scripts to
    the new version.

The library has been around for well over a year. A lot of improvements have
been made, a lot of user complaints have been fixed, and a lot of user desires
have been implemented. It's time to consider the public API as stable, and
remove some of the old methods that were around until now for compatibility
reasons. But there's one more surprise!

There is a new magic ``telethon.sync`` module to let you use **all** the
methods in the :ref:`TelegramClient <telethon-client>` (and the types returned
from its functions) in a synchronous way, while using `asyncio` behind
the scenes! This means you're now able to do both of the following:

.. code-block:: python

    import asyncio

    async def main():
      await client.send_message('me', 'Hello!')

    asyncio.get_event_loop().run_until_complete(main())

    # ...can be rewritten as:

    from telethon import sync
    client.send_message('me', 'Hello!')

Both ways can coexist (you need to ``await`` if the loop is running).

You can also use the magic ``sync`` module in your own classes, and call
``sync.syncify(cls)`` to convert all their ``async def`` into magic variants.



Breaking Changes
~~~~~~~~~~~~~~~~

- ``message.get_fwd_sender`` is now in `message.forward
  <telethon.tl.custom.message.Message.forward>`.
- ``client.idle`` is now `client.run_until_disconnected()
  <telethon.client.updates.UpdateMethods.run_until_disconnected>`
- ``client.add_update_handler`` is now `client.add_event_handler
  <telethon.client.updates.UpdateMethods.add_event_handler>`
- ``client.remove_update_handler`` is now `client.remove_event_handler
  <telethon.client.updates.UpdateMethods.remove_event_handler>`
- ``client.list_update_handlers`` is now `client.list_event_handlers
  <telethon.client.updates.UpdateMethods.list_event_handlers>`
- ``client.get_message_history`` is now `client.get_messages
  <telethon.client.messages.MessageMethods.get_messages>`
- ``client.send_voice_note`` is now `client.send_file
  <telethon.client.uploads.UploadMethods.send_file>` with ``is_voice=True``.
- ``client.invoke()`` is now ``client(...)``.
- ``report_errors`` has been removed since it's currently not used,
  and ``flood_sleep_threshold`` is now part of the client.
- The ``update_workers`` and ``spawn_read_thread`` arguments are gone.
  Simply remove them from your code when you create the client.
- Methods with a lot of arguments can no longer be used without specifying
  their argument. Instead you need to use named arguments. This improves
  readability and not needing to learn the order of the arguments, which
  can also change.


Additions
~~~~~~~~~

- `client.send_file <telethon.client.uploads.UploadMethods.send_file>` now
  accepts external ``http://`` and ``https://`` URLs.
- You can use the :ref:`TelegramClient <telethon-client>` inside of ``with``
  blocks, which will `client.start() <telethon.client.auth.AuthMethods.start>`
  and `disconnect() <telethon.client.telegrambaseclient.TelegramBaseClient.disconnect>`
  the client for you:

  .. code-block:: python

      from telethon import TelegramClient, sync

      with TelegramClient(name, api_id, api_hash) as client:
          client.send_message('me', 'Hello!')

  Convenience at its maximum! You can even chain the `.start()
  <telethon.client.auth.AuthMethods.start>` method since
  it returns the instance of the client:

  .. code-block:: python

      with TelegramClient(name, api_id, api_hash).start(bot_token=token) as bot:
          bot.send_message(chat, 'Hello!')


Bug fixes
~~~~~~~~~

- There were some ``@property async def`` left, and some ``await property``.
- "User joined" event was being treated as "User was invited".
- SQLite's cursor should not be closed properly after usage.
- ``await`` the updates task upon disconnection.
- Some bug in Python 3.5.2's `asyncio` causing 100% CPU load if you
  forgot to call `client.disconnect()
  <telethon.client.telegrambaseclient.TelegramBaseClient.disconnect>`.
  The method is called for you on object destruction, but you still should
  disconnect manually or use a ``with`` block.
- Some fixes regarding disconnecting on client deletion and properly
  saving the authorization key.
- Passing a class to `message.get_entities_text
  <telethon.tl.custom.message.Message.get_entities_text>` now works properly.
- Iterating messages from a specific user in private messages now works.

Enhancements
~~~~~~~~~~~~

- Both `client.start() <telethon.client.auth.AuthMethods.start>` and
  `client.run_until_disconnected()
  <telethon.client.updates.UpdateMethods.run_until_disconnected>` can
  be ran in both a synchronous way (without starting the loop manually)
  or from an ``async def`` where they need to have an ``await``.


Core Rewrite in asyncio (v1.0-rc1)
==================================

*Published at 2018/06/24*

+-----------------------+
| Scheme layer used: 81 |
+-----------------------+

This version is a major overhaul of the library internals. The core has
been rewritten, cleaned up and refactored to fix some oddities that have
been growing inside the library.

This means that the code is easier to understand and reason about,
including the code flow such as conditions, exceptions, where to
reconnect, how the library should behave, and separating different
retry types such as disconnections or call fails, but it also means
that **some things will necessarily break** in this version.

All requests that touch the network are now methods and need to
have their ``await`` (or be ran until their completion).

Also, the library finally has the simple logo it deserved: a carefully
hand-written ``.svg`` file representing a T following Python's colours.


Breaking Changes
~~~~~~~~~~~~~~~~

- If you relied on internals like the ``MtProtoSender`` and the
  ``TelegramBareClient``, both are gone. They are now `MTProtoSender
  <telethon.network.mtprotosender.MTProtoSender>` and `TelegramBaseClient
  <telethon.client.telegrambaseclient.TelegramBaseClient>` and they behave
  differently.
- Underscores have been renamed from filenames. This means
  ``telethon.errors.rpc_error_list`` won't work, but you should
  have been using `telethon.errors` all this time instead.
- `client.connect <telethon.client.telegrambaseclient.TelegramBaseClient.connect>`
  no longer returns `True` on success. Instead, you should ``except`` the
  possible ``ConnectionError`` and act accordingly. This makes it easier to
  not ignore the error.
- You can no longer set ``retries=n`` when calling a request manually. The
  limit works differently now, and it's done on a per-client basis.
- Accessing `.sender <telethon.tl.custom.message.Message.sender>`,
  `.chat <telethon.tl.custom.message.Message.chat>` and similar may *not* work
  in events anymore, since previously they could access the network. The new
  rule is that properties are not allowed to make API calls. You should use
  `.get_sender() <telethon.tl.custom.message.Message.get_sender>`,
  `.get_chat() <telethon.tl.custom.message.Message.get_chat>` instead while
  using events. You can safely access properties if you get messages through
  `client.get_messages() <telethon.client.messages.MessageMethods.get_messages>`
  or other methods in the client.
- The above point means ``reply_message`` is now `.get_reply_message()
  <telethon.tl.custom.message.Message.get_reply_message>`, and ``fwd_from_entity``
  is now `get_fwd_sender() <telethon.tl.custom.message.Message.get_fwd_sender>`.
  Also ``forward`` was gone in the previous version, and you should be using
  ``fwd_from`` instead.


Additions
~~~~~~~~~

- Telegram's Terms Of Service are now accepted when creating a new account.
  This can possibly help avoid bans. This has no effect for accounts that
  were created before.
- The `method reference <https://tl.telethon.dev/>`_ now shows
  which methods can be used if you sign in with a ``bot_token``.
- There's a new `client.disconnected
  <telethon.client.telegrambaseclient.TelegramBaseClient.disconnected>` future
  which you can wait on. When a disconnection occurs, you will now, instead
  letting it happen in the background.
- More configurable retries parameters, such as auto-reconnection, retries
  when connecting, and retries when sending a request.
- You can filter `events.NewMessage <telethon.events.newmessage.NewMessage>`
  by sender ID, and also whether they are forwards or not.
- New ``ignore_migrated`` parameter for `client.iter_dialogs
  <telethon.client.dialogs.DialogMethods.iter_dialogs>`.

Bug fixes
~~~~~~~~~

- Several fixes to `telethon.events.newmessage.NewMessage`.
- Removed named ``length`` argument in ``to_bytes`` for PyPy.
- Raw events failed due to not having ``._set_client``.
- `message.get_entities_text
  <telethon.tl.custom.message.Message.get_entities_text>` properly
  supports filtering, even if there are no message entities.
- `message.click <telethon.tl.custom.message.Message.click>` works better.
- The server started sending :tl:`DraftMessageEmpty` which the library
  didn't handle correctly when getting dialogs.
- The "correct" chat is now always returned from returned messages.
- ``to_id`` was not validated when retrieving messages by their IDs.
- ``'__'`` is no longer considered valid in usernames.
- The ``fd`` is removed from the reader upon closing the socket. This
  should be noticeable in Windows.
- :tl:`MessageEmpty` is now handled when searching messages.
- Fixed a rare infinite loop bug in `client.iter_dialogs
  <telethon.client.dialogs.DialogMethods.iter_dialogs>` for some people.
- Fixed ``TypeError`` when there is no `.sender
  <telethon.tl.custom.message.Message.sender>`.

Enhancements
~~~~~~~~~~~~

- You can now delete over 100 messages at once with `client.delete_messages
  <telethon.client.messages.MessageMethods.delete_messages>`.
- Signing in now accounts for ``AuthRestartError`` itself, and also handles
  ``PasswordHashInvalidError``.
- ``__all__`` is now defined, so ``from telethon import *`` imports sane
  defaults (client, events and utils). This is however discouraged and should
  be used only in quick scripts.
- ``pathlib.Path`` is now supported for downloading and uploading media.
- Messages you send to yourself are now considered outgoing, unless they
  are forwarded.
- The documentation has been updated with a brand new `asyncio` crash
  course to encourage you use it. You can still use the threaded version
  if you want though.
- ``.name`` property is now properly supported when sending and downloading
  files.
- Custom ``parse_mode``, which can now be set per-client, support
  :tl:`MessageEntityMentionName` so you can return those now.
- The session file is saved less often, which could result in a noticeable
  speed-up when working with a lot of incoming updates.


Internal changes
~~~~~~~~~~~~~~~~

- The flow for sending a request is as follows: the ``TelegramClient`` creates
  a ``MTProtoSender`` with a ``Connection``, and the sender starts send and
  receive loops. Sending a request means enqueueing it in the sender, which
  will eventually pack and encrypt it with its ``ConnectionState`` instead
  of using the entire ``Session`` instance. When the data is packed, it will
  be sent over the ``Connection`` and ultimately over the ``TcpClient``.

- Reconnection occurs at the ``MTProtoSender`` level, and receiving responses
  follows a similar process, but now ``asyncio.Future`` is used for the results
  which are no longer part of all ``TLObject``, instead are part of the
  ``TLMessage`` which simplifies things.

- Objects can no longer be ``content_related`` and instead subclass
  ``TLRequest``, making the separation of concerns easier.

- The ``TelegramClient`` has been split into several mixin classes to avoid
  having a 3,000-lines-long file with all the methods.

- More special cases in the ``MTProtoSender`` have been cleaned up, and also
  some attributes from the ``Session`` which didn't really belong there since
  they weren't being saved.

- The ``telethon_generator/`` can now convert ``.tl`` files into ``.json``,
  mostly as a proof of concept, but it might be useful for other people.


Custom Message class (v0.19.1)
==============================

*Published at 2018/06/03*

+-----------------------+
| Scheme layer used: 80 |
+-----------------------+


This update brings a new `telethon.tl.custom.message.Message` object!

All the methods in the `telethon.telegram_client.TelegramClient` that
used to return a :tl:`Message` will now return this object instead, which
means you can do things like the following:

.. code-block:: python

    msg = client.send_message(chat, 'Hello!')
    msg.edit('Hello there!')
    msg.reply('Good day!')
    print(msg.sender)

Refer to its documentation to see all you can do, again, click
`telethon.tl.custom.message.Message` to go to its page.


Breaking Changes
~~~~~~~~~~~~~~~~

- The `telethon.network.connection.common.Connection` class is now an ABC,
  and the old ``ConnectionMode`` is now gone. Use a specific connection (like
  `telethon.network.connection.tcpabridged.ConnectionTcpAbridged`) instead.

Additions
~~~~~~~~~

- You can get messages by their ID with
  `telethon.telegram_client.TelegramClient.get_messages`'s ``ids`` parameter:

  .. code-block:: python

      message = client.get_messages(chats, ids=123)  # Single message
      message_list = client.get_messages(chats, ids=[777, 778])  # Multiple

- More convenience properties for `telethon.tl.custom.dialog.Dialog`.
- New default `telethon.telegram_client.TelegramClient.parse_mode`.
- You can edit the media of messages that already have some media.
- New dark theme in the online ``tl`` reference, check it out at
  https://tl.telethon.dev/.

Bug fixes
~~~~~~~~~

- Some IDs start with ``1000`` and these would be wrongly treated as channels.
- Some short usernames like ``@vote`` were being ignored.
- `telethon.telegram_client.TelegramClient.iter_messages`'s ``from_user``
  was failing if no filter had been set.
- `telethon.telegram_client.TelegramClient.iter_messages`'s ``min_id/max_id``
  was being ignored by Telegram. This is now worked around.
- `telethon.telegram_client.TelegramClient.catch_up` would fail with empty
  states.
- `telethon.events.newmessage.NewMessage` supports ``incoming=False``
  to indicate ``outgoing=True``.

Enhancements
~~~~~~~~~~~~

- You can now send multiple requests at once while preserving the order:

  .. code-block:: python

      from telethon.tl.functions.messages import SendMessageRequest
      client([SendMessageRequest(chat, 'Hello 1!'),
              SendMessageRequest(chat, 'Hello 2!')], ordered=True)

Internal changes
~~~~~~~~~~~~~~~~

- ``without rowid`` is not used in SQLite anymore.
- Unboxed serialization would fail.
- Different default limit for ``iter_messages`` and ``get_messages``.
- Some clean-up in the ``telethon_generator/`` package.


Catching up on Updates (v0.19)
==============================

*Published at 2018/05/07*

+-----------------------+
| Scheme layer used: 76 |
+-----------------------+

This update prepares the library for catching up with updates with the new
`telethon.telegram_client.TelegramClient.catch_up` method. This feature needs
more testing, but for now it will let you "catch up" on some old updates that
occurred while the library was offline, and brings some new features and bug
fixes.


Additions
~~~~~~~~~

- Add ``search``, ``filter`` and ``from_user`` parameters to
  `telethon.telegram_client.TelegramClient.iter_messages`.
- `telethon.telegram_client.TelegramClient.download_file` now
  supports a `None` path to return the file in memory and
  return its `bytes`.
- Events now have a ``.original_update`` field.

Bug fixes
~~~~~~~~~

- Fixed a race condition when receiving items from the network.
- A disconnection is made when "retries reached 0". This hasn't been
  tested but it might fix the bug.
- ``reply_to`` would not override :tl:`Message` object's reply value.
- Add missing caption when sending :tl:`Message` with media.

Enhancements
~~~~~~~~~~~~

- Retry automatically on ``RpcCallFailError``. This error happened a lot
  when iterating over many messages, and retrying often fixes it.
- Faster `telethon.telegram_client.TelegramClient.iter_messages` by
  sleeping only as much as needed.
- `telethon.telegram_client.TelegramClient.edit_message` now supports
  omitting the entity if you pass a :tl:`Message`.
- `telethon.events.raw.Raw` can now be filtered by type.

Internal changes
~~~~~~~~~~~~~~~~

- The library now distinguishes between MTProto and API schemas.
- :tl:`State` is now persisted to the session file.
- Connection won't retry forever.
- Fixed some errors and cleaned up the generation of code.
- Fixed typos and enhanced some documentation in general.
- Add auto-cast for :tl:`InputMessage` and :tl:`InputLocation`.


Pickle-able objects (v0.18.3)
=============================

*Published at 2018/04/15*


Now you can use Python's ``pickle`` module to serialize ``RPCError`` and
any other ``TLObject`` thanks to **@vegeta1k95**! A fix that was fairly
simple, but still might be useful for many people.

As a side note, the documentation at https://tl.telethon.dev
now lists known ``RPCError`` for all requests, so you know what to expect.
This required a major rewrite, but it was well worth it!

Breaking changes
~~~~~~~~~~~~~~~~

- `telethon.telegram_client.TelegramClient.forward_messages` now returns
  a single item instead of a list if the input was also a single item.

Additions
~~~~~~~~~

- New `telethon.events.messageread.MessageRead` event, to find out when
  and who read which messages as soon as it happens.
- Now you can access ``.chat_id`` on all events and ``.sender_id`` on some.

Bug fixes
~~~~~~~~~

- Possibly fix some bug regarding lost ``GzipPacked`` requests.
- The library now uses the "real" layer 75, hopefully.
- Fixed ``.entities`` name collision on updates by making it private.
- ``AUTH_KEY_DUPLICATED`` is handled automatically on connection.
- Markdown parser's offset uses ``match.start()`` to allow custom regex.
- Some filter types (as a type) were not supported by
  `telethon.telegram_client.TelegramClient.iter_participants`.
- `telethon.telegram_client.TelegramClient.remove_event_handler` works.
- `telethon.telegram_client.TelegramClient.start` works on all terminals.
- :tl:`InputPeerSelf` case was missing from
  `telethon.telegram_client.TelegramClient.get_input_entity`.

Enhancements
~~~~~~~~~~~~

- The ``parse_mode`` for messages now accepts a callable.
- `telethon.telegram_client.TelegramClient.download_media` accepts web previews.
- `telethon.tl.custom.dialog.Dialog` instances can now be casted into
  :tl:`InputPeer`.
- Better logging when reading packages "breaks".
- Better and more powerful ``setup.py gen`` command.

Internal changes
~~~~~~~~~~~~~~~~

- The library won't call ``.get_dialogs()`` on entity not found. Instead,
  it will ``raise ValueError()`` so you can properly ``except`` it.
- Several new examples and updated documentation.
- ``py:obj`` is the default Sphinx's role which simplifies ``.rst`` files.
- ``setup.py`` now makes use of ``python_requires``.
- Events now live in separate files.
- Other minor changes.


Several bug fixes (v0.18.2)
===========================

*Published at 2018/03/27*

Just a few bug fixes before they become too many.

Additions
~~~~~~~~~

- Getting an entity by its positive ID should be enough, regardless of their
  type (whether it's an ``User``, a ``Chat`` or a ``Channel``). Although
  wrapping them inside a ``Peer`` is still recommended, it's not necessary.
- New ``client.edit_2fa`` function to change your Two Factor Authentication
  settings.
- ``.stringify()`` and string representation for custom ``Dialog/Draft``.

Bug fixes
~~~~~~~~~

- Some bug regarding ``.get_input_peer``.
- ``events.ChatAction`` wasn't picking up all the pins.
- ``force_document=True`` was being ignored for albums.
- Now you're able to send ``Photo`` and ``Document`` as files.
- Wrong access to a member on chat forbidden error for ``.get_participants``.
  An empty list is returned instead.
- ``me/self`` check for ``.get[_input]_entity`` has been moved up so if
  someone has "me" or "self" as their name they won't be retrieved.


Iterator methods (v0.18.1)
==========================

*Published at 2018/03/17*

All the ``.get_`` methods in the ``TelegramClient`` now have a ``.iter_``
counterpart, so you can do operations while retrieving items from them.
For instance, you can ``client.iter_dialogs()`` and ``break`` once you
find what you're looking for instead fetching them all at once.

Another big thing, you can get entities by just their positive ID. This
may cause some collisions (although it's very unlikely), and you can (should)
still be explicit about the type you want. However, it's a lot more convenient
and less confusing.

Breaking changes
~~~~~~~~~~~~~~~~

- The library only offers the default ``SQLiteSession`` again.
  See :ref:`sessions` for more on how to use a different storage from now on.

Additions
~~~~~~~~~

- Events now override ``__str__`` and implement ``.stringify()``, just like
  every other ``TLObject`` does.
- ``events.ChatAction`` now has :meth:`respond`, :meth:`reply` and
  :meth:`delete` for the message that triggered it.
- :meth:`client.iter_participants` (and its :meth:`client.get_participants`
  counterpart) now expose the ``filter`` argument, and the returned users
  also expose the ``.participant`` they are.
- You can now use :meth:`client.remove_event_handler` and
  :meth:`client.list_event_handlers` similar how you could with normal updates.
- New properties on ``events.NewMessage``, like ``.video_note`` and ``.gif``
  to access only specific types of documents.
- The ``Draft`` class now exposes ``.text`` and ``.raw_text``, as well as a
  new :meth:`Draft.send` to send it.

Bug fixes
~~~~~~~~~

- ``MessageEdited`` was ignoring ``NewMessage`` constructor arguments.
- Fixes for ``Event.delete_messages`` which wouldn't handle ``MessageService``.
- Bot API style IDs not working on :meth:`client.get_input_entity`.
- :meth:`client.download_media` didn't support ``PhotoSize``.

Enhancements
~~~~~~~~~~~~

- Less RPC are made when accessing the ``.sender`` and ``.chat`` of some
  events (mostly those that occur in a channel).
- You can send albums larger than 10 items (they will be sliced for you),
  as well as mixing normal files with photos.
- ``TLObject`` now have Python type hints.

Internal changes
~~~~~~~~~~~~~~~~

- Several documentation corrections.
- :meth:`client.get_dialogs` is only called once again when an entity is
  not found to avoid flood waits.


Sessions overhaul (v0.18)
=========================

*Published at 2018/03/04*

+-----------------------+
| Scheme layer used: 75 |
+-----------------------+

The ``Session``'s have been revisited thanks to the work of **@tulir** and
they now use an `ABC <https://docs.python.org/3/library/abc.html>`__ so you
can easily implement your own!

The default will still be a ``SQLiteSession``, but you might want to use
the new ``AlchemySessionContainer`` if you need. Refer to the section of
the documentation on :ref:`sessions` for more.

Breaking changes
~~~~~~~~~~~~~~~~

- ``events.MessageChanged`` doesn't exist anymore. Use the new
  ``events.MessageEdited`` and ``events.MessageDeleted`` instead.

Additions
~~~~~~~~~

- The mentioned addition of new session types.
- You can omit the event type on ``client.add_event_handler`` to use ``Raw``.
- You can ``raise StopPropagation`` of events if you added several of them.
- ``.get_participants()`` can now get up to 90,000 members from groups with
  100,000 if when ``aggressive=True``, "bypassing" Telegram's limit.
- You now can access ``NewMessage.Event.pattern_match``.
- Multiple captions are now supported when sending albums.
- ``client.send_message()`` has an optional ``file=`` parameter, so
  you can do ``events.reply(file='/path/to/photo.jpg')`` and similar.
- Added ``.input_`` versions to ``events.ChatAction``.
- You can now access the public ``.client`` property on ``events``.
- New ``client.forward_messages``, with its own wrapper on ``events``,
  called ``event.forward_to(...)``.


Bug fixes
~~~~~~~~~

- Silly bug regarding ``client.get_me(input_peer=True)``.
- ``client.send_voice_note()`` was missing some parameters.
- ``client.send_file()`` plays better with streams now.
- Incoming messages from bots weren't working with whitelists.
- Markdown's URL regex was not accepting newlines.
- Better attempt at joining background update threads.
- Use the right peer type when a marked integer ID is provided.


Internal changes
~~~~~~~~~~~~~~~~

- Resolving ``events.Raw`` is now a no-op.
- Logging calls in the ``TcpClient`` to spot errors.
- ``events`` resolution is postponed until you are successfully connected,
  so you can attach them before starting the client.
- When an entity is not found, it is searched in *all* dialogs. This might
  not always be desirable but it's more comfortable for legitimate uses.
- Some non-persisting properties from the ``Session`` have been moved out.


Further easing library usage (v0.17.4)
======================================

*Published at 2018/02/24*

Some new things and patches that already deserved their own release.


Additions
~~~~~~~~~

- New ``pattern`` argument to ``NewMessage`` to easily filter messages.
- New ``.get_participants()`` convenience method to get members from chats.
- ``.send_message()`` now accepts a ``Message`` as the ``message`` parameter.
- You can now ``.get_entity()`` through exact name match instead username.
- Raise ``ProxyConnectionError`` instead looping forever so you can
  ``except`` it on your own code and behave accordingly.

Bug fixes
~~~~~~~~~

- ``.parse_username`` would fail with ``www.`` or a trailing slash.
- ``events.MessageChanged`` would fail with ``UpdateDeleteMessages``.
- You can now send ``b'byte strings'`` directly as files again.
- ``.send_file()`` was not respecting the original captions when passing
  another message (or media) as the file.
- Downloading media from a different data center would always log a warning
  for the first time.

Internal changes
~~~~~~~~~~~~~~~~

- Use ``req_pq_multi`` instead ``req_pq`` when generating ``auth_key``.
- You can use ``.get_me(input_peer=True)`` if all you need is your self ID.
- New addition to the interactive client example to show peer information.
- Avoid special casing ``InputPeerSelf`` on some ``NewMessage`` events, so
  you can always safely rely on ``.sender`` to get the right ID.


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
  which you can find on https://pypi.org/project/cryptg/.



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
addition. Refer to *(removed broken link)* to get started with events.


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
- New exact match feature on https://tl.telethon.dev.
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
reuse requests that need "autocast" (e.g. you put :tl:`User` but ``InputPeer``
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
   `None` due to a race condition.
-  Correctly handle `None` dates when downloading media.
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
   avoid some `None` errors.
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
   the ``auth_key`` was `None` so this will ensure to have a valid
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
-  **Several worker threads** for your updates! By default, `None`
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
  as `false`!
- Another bug that didn't allow you to leave as `None` flag parameters
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
invoking something there (now it simply returns `None`).

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
~~~~~~~~~

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
~~~~~~~~~~~~

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
~~~~~~~~~

-  The mentioned different connection modes, and a new thread.
-  You can modify the ``Session`` attributes through the
   ``TelegramClient`` constructor (using ``**kwargs``).
-  ``RPCError``\ 's now belong to some request you've made, which makes
   more sense.
-  ``get_input_*`` now handles `None` (default) parameters more
   gracefully (it used to crash).

.. enhancements-4:

Enhancements
~~~~~~~~~~~~

-  The low-level socket doesn't use a handcrafted timeout anymore, which
   should benefit by avoiding the arbitrary ``sleep(0.1)`` that there
   used to be.
-  ``TelegramClient.sign_in`` will call ``.send_code_request`` if no
   ``code`` was provided.

Deprecation
~~~~~~~~~~~

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
~~~~~~~~~~~~~~~~

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
~~~~~~~~~

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
~~~~~~~~~

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
`InputPeer <https://tl.telethon.dev/types/input_peer.html>`__.
There also exist
`InputChannel <https://tl.telethon.dev/types/input_channel.html>`__
and
`InputUser <https://tl.telethon.dev/types/input_user.html>`__!
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
~~~~~~~~~~~~~~~~

-  Every Telegram error has now its **own class**, so it's easier to
   fine-tune your ``except``\ 's.
-  Markdown parsing is **not part** of Telethon itself anymore, although
   there are plans to support it again through a some external module.
-  The ``.list_sessions()`` has been moved to the ``Session`` class
   instead.
-  The ``InteractiveTelegramClient`` is **not** shipped with ``pip``
   anymore.

Additions
~~~~~~~~~

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
~~~~~~~~~

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
~~~~~~~~~~~~~~~~

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
  `here <https://tl.telethon.dev/>`__, has a new search bar.
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

It actually is a usable-enough client for your day by day. You could
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
