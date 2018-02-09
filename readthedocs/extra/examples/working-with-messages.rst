=====================
Working with messages
=====================


.. note::

    These examples assume you have read :ref:`accessing-the-full-api`.


Forwarding messages
*******************

Note that ForwardMessageRequest_ (note it's Message, singular) will *not*
work if channels are involved. This is because channel (and megagroups) IDs
are not unique, so you also need to know who the sender is (a parameter this
request doesn't have).

Either way, you are encouraged to use ForwardMessagesRequest_ (note it's
Message*s*, plural) *always*, since it is more powerful, as follows:

    .. code-block:: python

        from telethon.tl.functions.messages import ForwardMessagesRequest
        #                                             note the s ^

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

Messages are searched through the obvious SearchRequest_, but you may run
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
            from_id=None    # Who must have sent the message (peer)
        ))

It's important to note that the optional parameter ``from_id`` could have
been omitted (defaulting to ``None``). Changing it to InputUserEmpty_, as one
could think to specify "no user", won't work because this parameter is a flag,
and it being unspecified has a different meaning.

If one were to set ``from_id=InputUserEmpty()``, it would filter messages
from "empty" senders, which would likely match no users.

If you get a ``ChatAdminRequiredError`` on a channel, it's probably because
you tried setting the ``from_id`` filter, and as the error says, you can't
do that. Leave it set to ``None`` and it should work.

As with every method, make sure you use the right ID/hash combination for
your ``InputUser`` or ``InputChat``, or you'll likely run into errors like
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
        sticker_sets = client(GetAllStickersRequest(0))

        # Choose a sticker set
        sticker_set = sticker_sets.sets[0]

        # Get the stickers for this sticker set
        stickers = client(GetStickerSetRequest(
            stickerset=InputStickerSetID(
                id=sticker_set.id, access_hash=sticker_set.access_hash
            )
        ))

        # Stickers are nothing more than files, so send that
        client(SendMediaRequest(
            peer=client.get_me(),
            media=InputMediaDocument(
                id=InputDocument(
                    id=stickers.documents[0].id,
                    access_hash=stickers.documents[0].access_hash
                ),
                caption=''
            )
        ))


.. _ForwardMessageRequest: https://lonamiwebs.github.io/Telethon/methods/messages/forward_message.html
.. _ForwardMessagesRequest: https://lonamiwebs.github.io/Telethon/methods/messages/forward_messages.html
.. _SearchRequest: https://lonamiwebs.github.io/Telethon/methods/messages/search.html
.. _issues: https://github.com/LonamiWebs/Telethon/issues/215
.. _InputUserEmpty: https://lonamiwebs.github.io/Telethon/constructors/input_user_empty.html
