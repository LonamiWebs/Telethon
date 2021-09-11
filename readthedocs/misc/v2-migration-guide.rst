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

`Layer 133 <https://diff.telethon.dev/?from=132&to=133>`__ changed *a lot* of
identifiers from ``int`` to ``long``, meaning they will no longer fit in 32
bits, and instead require 64 bits.

If you were storing these identifiers somewhere size did matter (for example,
a database), you will need to migrate that to support the new size requirement
of 8 bytes.

For the full list of types changed, please review the above link.
