=====================
Working with messages
=====================


.. note::

    These examples assume you have read :ref:`accessing-the-full-api`.

.. contents::


Forwarding messages
*******************

.. note::

    Use the `telethon.client.messages.MessageMethods.forward_messages`
    friendly method instead unless you have a better reason not to!

    This method automatically accepts either a single message or many of them.

.. code-block:: python

    # If you only have the message IDs
    client.forward_messages(
        entity,  # to which entity you are forwarding the messages
        message_ids,  # the IDs of the messages (or message) to forward
        from_entity  # who sent the messages?
    )

    # If you have ``Message`` objects
    client.forward_messages(
        entity,  # to which entity you are forwarding the messages
        messages  # the messages (or message) to forward
    )

    # You can also do it manually if you prefer
    from telethon.tl.functions.messages import ForwardMessagesRequest

    messages = foo()  # retrieve a few messages (or even one, in a list)
    from_entity = bar()
    to_entity = baz()

    client(ForwardMessagesRequest(
        from_peer=from_entity,  # who sent these messages?
        id=[msg.id for msg in messages],  # which are the messages?
        to_peer=to_entity  # who are we forwarding them to?
    ))

The named arguments are there for clarity, although they're not needed because
they appear in order. You can obviously just wrap a single message on the list
too, if that's all you have.


Searching Messages
*******************

.. note::

    Use the `telethon.client.messages.MessageMethods.iter_messages`
    friendly method instead unless you have a better reason not to!

    This method has ``search`` and ``filter`` parameters that will
    suit your needs.

Messages are searched through the obvious :tl:`SearchRequest`, but you may run
into issues_. A valid example would be:

.. code-block:: python

    from telethon.tl.functions.messages import SearchRequest
    from telethon.tl.types import InputMessagesFilterEmpty

    filter = InputMessagesFilterEmpty()
    result = client(SearchRequest(
        peer=peer,      # On which chat/conversation
        q='query',      # What to search for
        filter=filter,  # Filter to use (maybe filter for media)
        min_date=None,  # Minimum date
        max_date=None,  # Maximum date
        offset_id=0,    # ID of the message to use as offset
        add_offset=0,   # Additional offset
        limit=10,       # How many results
        max_id=0,       # Maximum message ID
        min_id=0,       # Minimum message ID
        from_id=None,   # Who must have sent the message (peer)
        hash=0          # Special number to return nothing on no-change
    ))

It's important to note that the optional parameter ``from_id`` could have
been omitted (defaulting to ``None``). Changing it to :tl:`InputUserEmpty`, as one
could think to specify "no user", won't work because this parameter is a flag,
and it being unspecified has a different meaning.

If one were to set ``from_id=InputUserEmpty()``, it would filter messages
from "empty" senders, which would likely match no users.

If you get a ``ChatAdminRequiredError`` on a channel, it's probably because
you tried setting the ``from_id`` filter, and as the error says, you can't
do that. Leave it set to ``None`` and it should work.

As with every method, make sure you use the right ID/hash combination for
your :tl:`InputUser` or :tl:`InputChat`, or you'll likely run into errors like
``UserIdInvalidError``.


Sending stickers
****************

Stickers are nothing else than ``files``, and when you successfully retrieve
the stickers for a certain sticker set, all you will have are ``handles`` to
these files. Remember, the files Telegram holds on their servers can be
referenced through this pair of ID/hash (unique per user), and you need to
use this handle when sending a "document" message. This working example will
send yourself the very first sticker you have:

.. code-block:: python

    # Get all the sticker sets this user has
    from telethon.tl.functions.messages import GetAllStickersRequest
    sticker_sets = client(GetAllStickersRequest(0))

    # Choose a sticker set
    from telethon.tl.functions.messages import GetStickerSetRequest
    from telethon.tl.types import InputStickerSetID
    sticker_set = sticker_sets.sets[0]

    # Get the stickers for this sticker set
    stickers = client(GetStickerSetRequest(
        stickerset=InputStickerSetID(
            id=sticker_set.id, access_hash=sticker_set.access_hash
        )
    ))

    # Stickers are nothing more than files, so send that
    client.send_file('me', stickers.documents[0])


.. _issues: https://github.com/LonamiWebs/Telethon/issues/215
