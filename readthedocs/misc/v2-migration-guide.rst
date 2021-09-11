=========================
Version 2 Migration Guide
=========================

Version 2 represents the second major version change, breaking compatibility
with old code beyond the usual raw API changes in order to clean up a lot of
the technical debt that has grown on the project.

This document documents all the things you should be aware of when migrating
from Telethon version 1.x to 2.0 onwards.


User, chat and channel identifiers are now 64-bit numbers
---------------------------------------------------------

`Layer 133 <https://diff.telethon.dev/?from=132&to=133>`__ changed *a lot* of identifiers from
``int`` to ``long``, meaning they will no longer fit in 32 bits, and instead require 64 bits.

If you were storing these identifiers somewhere size did matter (for example, a database), you
will need to migrate that to support the new size requirement of 8 bytes.

For the full list of types changed, please review the above link.


Many modules are now private
----------------------------

There were a lot of things which were public but should not have been. From now on, you should
only rely on things that are either publicly re-exported or defined. That is, as soon as anything
starts with an underscore (``_``) on its name, you're acknowledging that the functionality may
change even across minor version changes, and thus have your code break.

* The ``telethon.client`` module is now ``telethon._client``, meaning you should stop relying on
  anything inside of it. This includes all of the subclasses that used to exist (like ``UserMethods``).


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
