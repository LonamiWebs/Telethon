.. _sending-requests:

==================
Sending Requests
==================

Since we're working with Python, one must not forget that they can do ``help(client)`` or ``help(TelegramClient)``
at any time for a more detailed description and a list of all the available methods.
Calling ``help()`` from an interactive Python session will always list all the methods for any object, even yours!

Interacting with the Telegram API is done through sending **requests**,
this is, any "method" listed on the API. There are a few methods on the ``TelegramClient`` class
that abstract you from the need of manually importing the requests you need.

For instance, retrieving your own user can be done in a single line:

    ``myself = client.get_me()``

Internally, this method has sent a request to Telegram, who replied with the information about your own user.

If you want to retrieve any other user, chat or channel (channels are a special subset of chats),
you want to retrieve their "entity". This is how the library refers to either of these:

    .. code-block:: python

        # The method will infer that you've passed an username
        # It also accepts phone numbers, and will get the user
        # from your contact list.
        lonami = client.get_entity('lonami')

Note that saving and using these entities will be more important when Accessing the Full API.
For now, this is a good way to get information about an user or chat.

Other common methods for quick scripts are also available:

    .. code-block:: python

        # Sending a message (use an entity/username/etc)
        client.send_message('TheAyyBot', 'ayy')

        # Sending a photo, or a file
        client.send_file(myself, '/path/to/the/file.jpg', force_document=True)

        # Downloading someone's profile photo. File is saved to 'where'
        where = client.download_profile_photo(someone)

        # Retrieving the message history
        total, messages, senders = client.get_message_history(someone)

        # Downloading the media from a specific message
        # You can specify either a directory, a filename, or nothing at all
        where = client.download_media(message, '/path/to/output')

Remember that you can call ``.stringify()`` to any object Telegram returns to pretty print it.
Calling ``str(result)`` does the same operation, but on a single line.
