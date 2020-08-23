=================
A Word of Warning
=================

Full API is **not** how you are intended to use the library. You **should**
always prefer the :ref:`client-ref`. However, not everything is implemented
as a friendly method, so full API is your last resort.

If you select a method in :ref:`client-ref`, you will most likely find an
example for that method. This is how you are intended to use the library.

Full API **will** break between different minor versions of the library,
since Telegram changes very often. The friendly methods will be kept
compatible between major versions.

If you need to see real-world examples, please refer to the
`wiki page of projects using Telethon <https://github.com/LonamiWebs/Telethon/wiki/Projects-using-Telethon>`__.
