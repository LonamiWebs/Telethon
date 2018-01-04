.. _telegram-client:

==============
TelegramClient
==============


Introduction
************

The ``TelegramClient`` is the central class of the library, the one
you will be using most of the time. For this reason, it's important
to know what it offers.

Since we're working with Python, one must not forget that we can do
``help(client)`` or ``help(TelegramClient)`` at any time for a more
detailed description and a list of all the available methods. Calling
``help()`` from an interactive Python session will always list all the
methods for any object, even yours!

Interacting with the Telegram API is done through sending **requests**,
this is, any "method" listed on the API. There are a few methods (and
growing!) on the ``TelegramClient`` class that abstract you from the
need of manually importing the requests you need.

For instance, retrieving your own user can be done in a single line:

    ``myself = client.get_me()``

Internally, this method has sent a request to Telegram, who replied with
the information about your own user, and then the desired information
was extracted from their response.

If you want to retrieve any other user, chat or channel (channels are a
special subset of chats), you want to retrieve their "entity". This is
how the library refers to either of these:

    .. code-block:: python

        # The method will infer that you've passed an username
        # It also accepts phone numbers, and will get the user
        # from your contact list.
        lonami = client.get_entity('lonami')

The so called "entities" are another important whole concept on its own,
and you should
Note that saving and using these entities will be more important when
Accessing the Full API. For now, this is a good way to get information
about an user or chat.

Other common methods for quick scripts are also available:

    .. code-block:: python

        # Sending a message (use an entity/username/etc)
        client.send_message('TheAyyBot', 'ayy')

        # Sending a photo, or a file
        client.send_file(myself, '/path/to/the/file.jpg', force_document=True)

        # Downloading someone's profile photo. File is saved to 'where'
        where = client.download_profile_photo(someone)

        # Retrieving the message history
        messages = client.get_message_history(someone)

        # Downloading the media from a specific message
        # You can specify either a directory, a filename, or nothing at all
        where = client.download_media(message, '/path/to/output')

        # Call .disconnect() when you're done
        client.disconnect()

Remember that you can call ``.stringify()`` to any object Telegram returns
to pretty print it. Calling ``str(result)`` does the same operation, but on
a single line.


Available methods
*****************

This page lists all the "handy" methods available for you to use in the
``TelegramClient`` class. These are simply wrappers around the "raw"
Telegram API, making it much more manageable and easier to work with.

Please refer to :ref:`accessing-the-full-api` if these aren't enough,
and don't be afraid to read the source code of the InteractiveTelegramClient_
or even the TelegramClient_ itself to learn how it works.


.. _InteractiveTelegramClient: https://github.com/LonamiWebs/Telethon/blob/master/telethon_examples/interactive_telegram_client.py
.. _TelegramClient: https://github.com/LonamiWebs/Telethon/blob/master/telethon/telegram_client.py



.. automodule:: telethon.telegram_client
    :members:
    :undoc-members:
    :show-inheritance:
