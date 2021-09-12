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


Pyhton 3.5 is no longer supported
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


The Conversation API has been removed
-------------------------------------

This API had certain shortcomings, such as lacking persistence, poor interaction with other event
handlers, and overcomplicated usage for anything beyond the simplest case.

It is not difficult to write your own code to deal with a conversation's state. A simple
`Finite State Machine <https://stackoverflow.com/a/62246569/>`__ inside your handlers will do
just fine This approach can also be easily persisted, and you can adjust it to your needs and
your handlers much more easily.

// TODO provide standalone alternative for this?


The TelegramClient is no longer made out of mixins
--------------------------------------------------

If you were relying on any of the individual mixins that made up the client, such as
``UserMethods`` inside the ``telethon.client`` subpackage, those are now gone.
There is a single ``TelegramClient`` class now, containing everything you need.
