The Full API
============

.. currentmodule:: telethon

The API surface offered by Telethon is not exhaustive.
Telegram is constantly adding new features, and both implementing and documenting custom methods would an exhausting, never-ending job.

Telethon concedes to this fact and implements only commonly-used features to keep a lean API.
Access to the entirity of Telegram's API via Telethon's :term:`Raw API` is a necessary evil.

The ``telethon._tl`` module has a leading underscore to signal that it is private.
It is not covered by the semver guarantees of the library, but you may need to use it regardless.
If the :class:`Client` doesn't offer a method for what you need, using the :term:`Raw API` is inevitable.


Invoking Raw API methods
------------------------

The :term:`Raw API` can be *invoked* in a very similar way to other client methods:

.. code-block:: python

    from telethon import _tl as tl

    was_reset = await client(tl.functions.account.reset_wall_papers())

Inside ``telethon._tl.functions`` you will find a function for every single :term:`RPC` supported by Telegram.
The parameters are keyword-only and do not have defaults.
Whatever arguments you pass is exactly what Telegram will receive.
Whatever is returned is exactly what Telegram responded with.

All functions inside ``telethon._tl.functions`` will return the serialized request.
When calling a :class:`Client` instance with this request as input, it will be sent to Telegram and wait for a response.

Multiple requests may be in-flight at the same time, specially when using :mod:`asyncio`.
Telethon will attempt to combine these into a single "container" when possible as an optimization.


Exploring the Raw API
---------------------

Everything under ``telethon._tl.types`` implements :func:`repr`.
This means you can print any response and get the Python representation of that object.

All types are proper classes with attributes.
You do not need to use a regular expression on the string representation to access the field you want.

Most :term:`RPC` return an abstract class from ``telethon._tl.abcs``.
To check for a concrete type, you can use :func:`isinstance`:

.. code-block:: python

    invite = await client(tl.functions.messages.check_chat_invite(hash='aBcDeF'))
    if isinstance(invite, tl.types.ChatInviteAlready):
        print(invite.chat)

The ``telethon._tl`` module is not documented here because it would result in tens of megabytes.
Instead, there are multiple alternatives:

* Use Telethon's separate site to search in the `Telethon Raw API <https://tl.telethon.dev/>`_.
  This is the recommended way. It also features auto-generated examples.
* Use Python's built-in :func:`help` and :func:`dir` to help you navigate the module.
* Use an editor with autocompletion support.
* Choose the right layer from `Telegram's official API Layers <https://core.telegram.org/api/layers>`_.
  Note that the `TL Schema <https://core.telegram.org/schema>`_ might not be up-to-date.
