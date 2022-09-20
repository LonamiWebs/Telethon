.. _rpc-errors:

==========
RPC Errors
==========

RPC stands for Remote Procedure Call, and when the library raises
a ``RPCError``, it's because you have invoked some of the API
methods incorrectly (wrong parameters, wrong permissions, or even
something went wrong on Telegram's server).

You should import the errors from ``telethon.errors`` like so:

.. code-block:: python

    from telethon import errors

    try:
        async with client.takeout() as takeout:
            ...

    except errors.TakeoutInitDelayError as e:
        #  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^ here we except TAKEOUT_INIT_DELAY
        print('Must wait', e.seconds, 'before takeout')


There isn't any official list of all possible RPC errors, so the
`list of known errors`_ is provided on a best-effort basis. When new methods
are available, the list may be lacking since we simply don't know what errors
can raise from them.

Once we do find out about a new error and what causes it, the list is
updated, so if you see an error without a specific class, do report it
(and what method caused it)!.

This list is used to generate documentation for the `raw API page`_.
For example, if we want to know what errors can occur from
`messages.sendMessage`_ we can simply navigate to its raw API page
and find it has 24 known RPC errors at the time of writing.


Base Errors
===========

All the "base" errors are listed in :ref:`telethon-errors`.
Any other more specific error will be a subclass of these.

If the library isn't aware of a specific error just yet, it will instead
raise one of these superclasses. This means you may find stuff like this:

.. code-block:: text

    telethon.errors.rpcbaseerrors.BadRequestError: RPCError 400: MESSAGE_POLL_CLOSED (caused by SendVoteRequest)

If you do, make sure to open an issue or send a pull request to update the
`list of known errors`_.


Common Errors
=============

These are some of the errors you may normally need to deal with:

-  ``FloodWaitError`` (420), the same request was repeated many times.
   Must wait ``.seconds`` (you can access this attribute). For example:

   .. code-block:: python

       ...
       from telethon import errors

       try:
           messages = await client.get_messages(chat)
           print(messages[0].text)
       except errors.FloodWaitError as e:
           print('Have to sleep', e.seconds, 'seconds')
           time.sleep(e.seconds)

-  ``SessionPasswordNeededError``, if you have setup two-steps
   verification on Telegram and are trying to sign in.
-  ``FilePartMissingError``, if you have tried to upload an empty file.
-  ``ChatAdminRequiredError``, you don't have permissions to perform
   said operation on a chat or channel. Try avoiding filters, i.e. when
   searching messages.

The generic classes for different error codes are:

- ``InvalidDCError`` (303), the request must be repeated on another DC.
- ``BadRequestError`` (400), the request contained errors.
- ``UnauthorizedError`` (401), the user is not authorized yet.
- ``ForbiddenError`` (403), privacy violation error.
- ``NotFoundError`` (404), make sure you're invoking ``Request``\ 's!

If the error is not recognised, it will only be an ``RPCError``.

You can refer to all errors from Python through the ``telethon.errors``
module. If you don't know what attributes they have, try printing their
dir (like ``print(dir(e))``).


Attributes
==========

Some of the errors carry additional data in them. When they look like
``EMAIL_UNCONFIRMED_X``, the ``_X`` value will be accessible from the
error instance. The current list of errors that do this is the following:

- ``EmailUnconfirmedError`` has ``.code_length``.
- ``FileMigrateError`` has ``.new_dc``.
- ``FilePartMissingError`` has ``.which``.
- ``FloodTestPhoneWaitError`` has ``.seconds``.
- ``FloodWaitError`` has ``.seconds``.
- ``InterdcCallErrorError`` has ``.dc``.
- ``InterdcCallRichErrorError`` has ``.dc``.
- ``NetworkMigrateError`` has ``.new_dc``.
- ``PhoneMigrateError`` has ``.new_dc``.
- ``SlowModeWaitError`` has ``.seconds``.
- ``TakeoutInitDelayError`` has ``.seconds``.
- ``UserMigrateError`` has ``.new_dc``.


Avoiding Limits
===============

Don't spam. You won't get ``FloodWaitError`` or your account banned or
deleted if you use the library *for legit use cases*. Make cool tools.
Don't spam! Nobody knows the exact limits for all requests since they
depend on a lot of factors, so don't bother asking.

Still, if you do have a legit use case and still get those errors, the
library will automatically sleep when they are smaller than 60 seconds
by default. You can set different "auto-sleep" thresholds:

.. code-block:: python

    client.flood_sleep_threshold = 0  # Don't auto-sleep
    client.flood_sleep_threshold = 24 * 60 * 60  # Sleep always

You can also except it and act as you prefer:

.. code-block:: python

    from telethon.errors import FloodWaitError
    try:
        ...
    except FloodWaitError as e:
        print('Flood waited for', e.seconds)
        quit(1)

VoIP numbers are very limited, and some countries are more limited too.


.. _list of known errors: https://github.com/LonamiWebs/Telethon/blob/v1/telethon_generator/data/errors.csv
.. _raw API page: https://tl.telethon.dev/
.. _messages.sendMessage: https://tl.telethon.dev/methods/messages/send_message.html
