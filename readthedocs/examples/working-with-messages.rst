=====================
Working with messages
=====================


.. note::

    These examples assume you have read :ref:`full-api`.

.. contents::


Sending stickers
================

Stickers are nothing else than ``files``, and when you successfully retrieve
the stickers for a certain sticker set, all you will have are ``handles`` to
these files. Remember, the files Telegram holds on their servers can be
referenced through this pair of ID/hash (unique per user), and you need to
use this handle when sending a "document" message. This working example will
send yourself the very first sticker you have:

.. code-block:: python

    # Get all the sticker sets this user has
    from telethon.tl.functions.messages import GetAllStickersRequest
    sticker_sets = await client(GetAllStickersRequest(0))

    # Choose a sticker set
    from telethon.tl.functions.messages import GetStickerSetRequest
    from telethon.tl.types import InputStickerSetID
    sticker_set = sticker_sets.sets[0]

    # Get the stickers for this sticker set
    stickers = await client(GetStickerSetRequest(
        stickerset=InputStickerSetID(
            id=sticker_set.id, access_hash=sticker_set.access_hash
        )
    ))

    # Stickers are nothing more than files, so send that
    await client.send_file('me', stickers.documents[0])


.. _issues: https://github.com/LonamiWebs/Telethon/issues/215
