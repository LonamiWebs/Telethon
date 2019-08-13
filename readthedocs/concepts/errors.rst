.. _rpc-errors:

==========
RPC Errors
==========

RPC stands for Remote Procedure Call, and when the library raises
a ``RPCError``, it's because you have invoked some of the API
methods incorrectly (wrong parameters, wrong permissions, or even
something went wrong on Telegram's server). All the errors are
available in :ref:`telethon-errors`, but some examples are:

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
   verification on Telegram.
-  ``CdnFileTamperedError``, if the media you were trying to download
   from a CDN has been altered.
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
