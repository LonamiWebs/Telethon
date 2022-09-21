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


Sending reactions
=================

It works very similar to replying to a message. You need to specify the chat,
message ID you wish to react to, and reaction, using :tl:`SendReaction`:

.. code-block:: python

    from telethon.tl.functions.messages import SendReactionRequest

    await client(SendReactionRequest(
        peer=chat,
        msg_id=42,
        reaction='❤️'
    ))

Note that you cannot use strings like ``:heart:`` for the reaction. You must
use the desired emoji directly. You can most easily achieve this by
copy-pasting the emoji from an official application such as Telegram Desktop.

If for some reason you cannot embed emoji directly into the code, you can also
use its unicode escape (which you can find using websites like
`unicode-table.com`_), or install a different package, like `emoji`_:

.. code-block:: python

    # All of these work exactly the same (you only need one):
    import emoji
    reaction = emoji.emojize(':red_heart:')
    reaction = '❤️'
    reaction = '\u2764'

    from telethon.tl.functions.messages import SendReactionRequest
    await client(SendReactionRequest(
        peer=chat,
        msg_id=42,
        reaction=reaction
    ))

Please make sure to check the help pages of the respective websites you use
if you need a more in-depth explanation on how they work. Telethon only needs
you to provide the emoji in some form. Some packages or websites can make this
easier.

.. _unicode-table.com: https://unicode-table.com/en/emoji/
.. _emoji: https://pypi.org/project/emoji/
