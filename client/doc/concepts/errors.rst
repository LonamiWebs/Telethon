RPC Errors
==========

.. currentmodule:: telethon

:term:`RPC` stands for Remote Procedure Call.
By extension, RPC Errors occur when a RPC fails to execute in the server.
In Telethon, a :term:`RPC error` corresponds to the :class:`RpcError` class.

Telethon will only ever raise :class:`RpcError` when the result to a :term:`RPC` is an error.
If the error is raised, you know it comes from Telegram.
Consequently, when using :term:`Raw API` directly, if a :class:`RpcError` occurs, it is *extremely unlikely* to be a bug in the library.
When :class:`RpcError`\ s are raised using the :term:`Raw API`, Telegram is the one that decided an error should occur.

:term:`RPC error` consist of an integer :attr:`~RpcError.code` and a string :attr:`~RpcError.name`.
The :attr:`RpcError.code` is roughly the same as `HTTP status codes <https://developer.mozilla.org/en-US/docs/Web/HTTP/Status>`_.
The :attr:`RpcError.name` is often a string in ``SCREAMING_CASE`` and refers to what went wrong.

Certain error names also contain an integer value.
This value is removed from the :attr:`~RpcError.name` and put into :attr:`RpcError.value`.
If Telegram responds with ``FLOOD_WAIT_60``, the name would be ``'FLOOD_WAIT'`` and the value ``60``.

A very common error is ``FLOOD_WAIT``.
It occurs when you have attempted to use a request too many times during a certain window of time:

.. code-block:: python

    import asyncio
    from telethon import errors

    try:
        await client.send_message('me', 'Spam')
    except errors.FloodWait as e:
        # A flood error; sleep.
        await asyncio.sleep(e.value)

Note that the library can automatically handle and retry on ``FLOOD_WAIT`` for you.
Refer to the ``flood_sleep_threshold`` of the :class:`Client` to learn how.

Refer to the documentation of the :data:`telethon.errors` pseudo-module for more details.
