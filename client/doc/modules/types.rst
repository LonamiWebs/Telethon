Types
=====

This section contains most custom types used by the library.
:doc:`events` and the :doc:`client` get their own section to prevent the page from growing out of control.

Some of these are further divided into additional submodules.
This keeps them neatly grouped and avoids polluting a single module too much.


Core types
----------

.. automodule:: telethon.types


Keyboard buttons
----------------

.. automodule:: telethon.types.buttons


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

    Note how the :attr:`RpcError.value` field is still accessible, as it's a subclass of :class:`RpcError`.
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

Private definitions
-------------------

.. warning::

    These are **not** intended to be imported directly.
    They are *not* available from :mod:`telethon.types`.

    This section exists for documentation purposes only.

.. currentmodule:: telethon._impl.client.types.async_list

.. data:: T

    Generic parameter used by :class:`AsyncList`.

.. currentmodule:: telethon._impl.client.types.file

.. autoclass:: InFileLike

.. autoclass:: OutFileLike

.. currentmodule:: telethon._impl.mtsender.sender

.. autoclass:: AsyncReader

.. autoclass:: AsyncWriter

.. autoclass:: Connector
