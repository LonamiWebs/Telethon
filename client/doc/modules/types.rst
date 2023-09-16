Types
=====

.. automodule:: telethon.types

Errors
------

.. autoclass:: telethon.RpcError

.. currentmodule:: telethon

.. data:: errors

    Factory-object returning subclasses of :class:`RpcError`.

    You can think of it as a module with an infinite amount of error types in it.

    When accessing any attribute in this object, a subclass of :class:`RpcError` will be returned.

    The returned type will catch :class:`RpcError` if the :attr:`RpcError.name` matches the attribute converted to ``SCREAMING_CASE``.

    For example:

    .. code-block:: python

        from telethon import errors

        try:
            await client.send_message(chat, text)
        except errors.FloodWait as e:
            await asyncio.sleep(e.value)

    The code above is equivalent to the following:

    .. code-block:: python

        from telethon import RpcError

        try:
            await client.send_message(chat, text)
        except RpcError as e:
            if e.name == 'FLOOD_WAIT':
                await asyncio.sleep(e.value)
            else:
                raise

    This factory object is merely a convenience.

    There is one exception, and that is when the attribute name starts with ``'Code'`` and ends with a number:

    .. code-block:: python

        try:
            await client.send_message(chat, text)
        except errors.Code420:
            await asyncio.sleep(e.value)

    The above snippet is equivalent to checking :attr:`RpcError.code` instead:

    .. code-block:: python

        try:
            await client.send_message(chat, text)
        except RpcError as e:
            if e.code == 420:
                await asyncio.sleep(e.value)
            else:
                raise
