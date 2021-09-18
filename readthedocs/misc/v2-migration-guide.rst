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

The library will no longer attempt to support Python 3.5. The minimum version is now Python 3.6.


User, chat and channel identifiers are now 64-bit numbers
---------------------------------------------------------

`Layer 133 <https://diff.telethon.dev/?from=132&to=133>`__ changed *a lot* of identifiers from
``int`` to ``long``, meaning they will no longer fit in 32 bits, and instead require 64 bits.

If you were storing these identifiers somewhere size did matter (for example, a database), you
will need to migrate that to support the new size requirement of 8 bytes.

For the full list of types changed, please review the above link.


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


Raw API methods have been renamed and are now considered private
----------------------------------------------------------------

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

// TODO this definitely generated files mapping from the original name to this new one...


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

// TODO provide the new clean utils


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

In order to avoid breaking more code than strictly necessary, ``.raw_text`` will remain a synonym
of ``.message``, and ``.text`` will still be the text formatted through the ``client.parse_mode``.
However, you're encouraged to change uses of ``.raw_text`` with ``.message``, and ``.text`` with
either ``.md_text`` or ``.html_text`` as needed. This is because both ``.text`` and ``.raw_text``
may disappear in future versions, and their behaviour is not immediately obvious.


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


The aggressive parameter hack has been removed
----------------------------------------------

The "aggressive" hack in ``get_participants`` (and ``iter_participants``) is now gone.
It was not reliable, and was a cause of flood wait errors.


The total value when getting participants has changed
-----------------------------------------------------

Before, it used to always be the total amount of people inside the chat. Now the filter is also
considered. If you were running ``client.get_participants`` with a ``filter`` other than the
default and accessing the ``list.total``, you will now get a different result. You will need to
perform a separate request with no filter to fetch the total without filter (this is what the
library used to do).


Using message.edit will now raise an error if the message cannot be edited
--------------------------------------------------------------------------

Before, calling ``message.edit()`` would completely ignore your attempt to edit a message if the
message had a forward header or was not outgoing. This is no longer the case. It is now the user's
responsibility to check for this.

However, most likely, you were already doing the right thing (or else you would've experienced a
"why is this not being edited", which you would most likely consider a bug rather than a feature).


The TelegramClient is no longer made out of mixins
--------------------------------------------------

If you were relying on any of the individual mixins that made up the client, such as
``UserMethods`` inside the ``telethon.client`` subpackage, those are now gone.
There is a single ``TelegramClient`` class now, containing everything you need.


CdnDecrypter has been removed
-----------------------------

It was not really working and was more intended to be an implementation detail than anything else.
