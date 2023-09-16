Migrating from v1 to v2
=======================

.. currentmodule:: telethon

v2 is a complete reboot of Telethon v1.
Because a lot of the library has suffered radical changes, there are no plans to provide "bridge" methods emulating the old interface.
Doing so would take a lot of extra time and energy, and it's honestly not fun.

What this means is that your v1 code very likely won't run in v2.
Sorry.
I hope you can use this opportunity to shake up your dusty code into a cleaner design, too.

The common theme in v2 could be described as "no bullshit".

v1 had grown a lot of features.
A lot of them did a lot of things, at all once, in slightly different ways.
Semver allows additions, so v2 will start out smaller and grow in a controlled manner.

Custom types were a frankestein monster, combining both raw and manually-defined properties in hacky ways.
Type hinting was an unmaintained disaster.
Features such as file IDs, proxies and a lot of utilities were pretty much abandoned.

The several attempts at making v2 a reality over the years starting from the top did not work out.
A bottom-up approach was needed.
So a full rewrite was warranted.

TLSharp was Telethon's seed.
Telethon v0 was needed to learn Python at all.
Telethon v1 was necessary to learn what was a good design, and what wasn't.
This inspired `grammers <https://gramme.rs>`_, a Rust re-implementation with a thought-out design.
Telethon v2 completes the loop by porting grammers back to Python, now built with years of experience in the Telegram protocol.

It turns out static type checking is a very good idea for long-running projects.
So I strongly encourage you to use `mypy <https://www.mypy-lang.org/>`_ when developing code with Telethon v2.
I can guarantee you will into far less problems.

Without further ado, let's take a look at the biggest changes.
This list may not be exhaustive, but it should give you an idea on what to expect.


Complete project restructure
----------------------------

The public modules under the ``telethon`` now make actual sense.

* The root ``telethon`` package contains the basics like the :class:`Client` and :class:`RpcError`.
* :mod:`telethon.types` contains all the types, for your tpye-hinting needs.
* :mod:`telethon.events` contains all the events.
* :mod:`telethon.events.filters` contains all the event filters.
* :mod:`telethon.session` contains the session storages, should you choose to build a custom one.
* :data:`telethon.errors` is no longer a module.
  It's actually a factory object returning new error types on demand.
  This means you don't need to wait for new library versions to be released to catch them.

This was also a good opportunity to remove a lot of modules that were not supposed to public in their entirety:
``.crypto``, ``.extensions``, ``.network``, ``.custom``, ``.functions``, ``.helpers``, ``.hints``, ``.password``, ``.requestiter``, ``.sync``, ``.types``, ``.utils``.


Raw API is now private
----------------------

v2 aims to comply with `Semantic Versioning <https://semver.org/>`.
This is impossible because Telegram is a live service that can change things any time.
But we can get pretty close.

In v1, minor version changes bumped Telegram's :term:`layer`.
This technically violated semver, because they were part of a public module.

To allow for new layers to be added without the need for major releases, ``telethon._tl`` is instead private.
Here's the recommended way to import and use it now:

.. code-block:: python

    from telethon import _tl as tl

    was_reset = await client(tl.functions.account.reset_wall_papers())

    if isinstance(chat, tl.abcs.User):
        if isinstance(chat, tl.types.UserEmpty):
            return
        # chat is tl.types.User

There are three modules (four, if you count ``core``, which you probably should not use).
Each of them can have an additional namespace (as seen above with ``account.``).

* ``tl.functions`` contains every :term:`TL` definition treated as a function.
  The naming convention now follows Python's, and are ``snake_case``.
  They're no longer a class with attributes.
  They serialize the request immediately.
* ``tl.abcs`` contains every abstract class, the "boxed" types from Telegram.
  You can use these for your type-hinting needs.
* ``tl.types`` contains concrete instances, the "bare" types Telegram actually returns.
  You'll probably use these with :func:`isinstance` a lot.
  All types use :term:`__slots__` to save space.
  This means you can't add extra fields to these at runtime unless you subclass.


Unified client iter and get methods
-----------------------------------

The client no longer has ``client.iter_...`` methods.

Instead, the return a type that supports both :keyword:`await` and :keyword:`async for`:

.. code-block:: python

    messages = await client.get_messages(chat, 100)
    # or
    async for message in client.get_messages(chat, 100):
        ...

.. note::

    :meth:`Client.get_messages` no longer has funny rules for the ``limit`` either.
    If you ``await`` it without limit, it will probably take a long time to complete.
    This is in contrast to v1, where ``get`` defaulted to 1 message and ``iter`` to no limit.


Removed client methods and properties
-------------------------------------

.. rubric:: No ``client.parse_mode`` property.

Instead, you need to specify how the message text should be interpreted every time.
In :meth:`~Client.send_message`, use ``text=``, ``markdown=`` or ``html=``.
In :meth:`~Client.send_file` and friends, use one of the ``caption`` parameters.

.. rubric:: No ``client.loop`` property.

Instead, you can use :func:`asyncio.get_running_loop`.

.. rubric:: No ``client.conversation()`` method.

Instead, you will need to `design your own FSM <https://stackoverflow.com/a/62246569>`_.
The simplest approach could be using a global ``states`` dictionary storing the next function to call:

.. code-block:: python

    from functools import partial

    states = {}

    @client.on(events.NewMessage)
    async def conversation_entry_point(event):
        if fn := state.get(event.sender.id):
            await fn(event)
        else:
            await event.respond('Hi! What is your name?')
            state[event.sender.id] = handle_name

    async def handle_name(event):
        await event.respond('What is your age?')
        states[event.sender.id] = partial(handle_age, name=event.text)

    async def handle_age(event, name):
        age = event.text
        await event.respond(f'Hi {name}, I am {age} too!')
        del states[event.sender.id]



No message.raw_text or message.message
--------------------------------------

Messages no longer have ``.raw_text`` or ``.message`` properties.

Instead, you can access the :attr:`types.Message.text`,
:attr:`~types.Message.text_markdown` or :attr:`~types.Message.text_html`.
These names aim to be consistent with ``caption_markdown`` and ``caption_html``.

In v1, messages coming from a client used that client's parse mode as some sort of "global state".
Based on the client's parse mode, v1 ``message.text`` property would return different things.
But not *all* messages did this!
Those coming from the raw API had no client, so ``text`` couldn't know how to format the message.

Overall, the old design made the parse mode be pretty hidden.
This was not very intuitive and also made it very awkward to combine multiple parse modes.


Event and filters are now separate
----------------------------------

Event types are no longer callable and do not have filters inside them.
There is no longer nested ``class Event`` inside them either.

Instead, the event type itself is what the handler will actually be called with.
Because filters are separate, there is no longer a need for v1 ``@events.register`` either.

Filters are now normal functions that work with any event.
Of course, this doesn't mean all filters make sense for all events.
But you can use them in an unified manner.

Filters no longer support asynchronous operations, which removes a footgun.
This was most commonly experienced when using usernames as the ``chats`` filter in v1, and getting flood errors you couldn't handle.
In v2, you must pass a list of identifiers.
This means getting those identifiers is up to you, and you can handle it in a way that is appropriated for your application.

.. seealso::

    In-depth explanation for :doc:`/concepts/updates`.


Streamlined chat, input_chat and chat_id
----------------------------------------

The same goes for ``sender``, ``input_sender`` and ``sender_id``.
And also for ``get_chat``, ``get_input_chat``, ``get_sender`` and ``get_input_sender``.
Yeah, it was bad.

Instead, events with chat information now *always* have a ``.chat``, with *at least* the ``.id``.
The same is true for the ``.sender``, as long as the event has one with at least the user identifier.

This doesn't mean the ``.chat`` or ``.sender`` will have all the information.
Telegram may still choose to send their ``min`` version with only basic details.
But it means you don't have to remember 5 different ways of using chats.

To replace the concept of "input chats", v2 introduces :class:`types.PackedChat`.
A "packed chat" is a chat with *just* enough information that you can use it without relying on Telethon's cache.
This is the most efficient way to call methods like :meth:`Client.send_message` too.

The concept of "marked IDs" also no longer exists.
This means v2 no longer supports the ``-`` or ``-100`` prefixes on identifiers.
:tl:`Peer`-wrapping is gone, too.
Instead, you're strongly encouraged to use :class:`types.PackedChat` instances.

The concepts of of "entity" or "peer" are unified to simply :term:`chat`.
Overall, dealing with users, groups and channels should feel a lot more natural.

.. seealso::

    In-depth explanation for :doc:`/concepts/chats`.


Session cache no longer exists
------------------------------

At least, not the way it did before.

The v1 cache that allowed you to use just chat identifiers to call methods is no longer saved to disk.

Sessions now only contain crucial information to have a working client.
This includes the server address, authorization key, update state, and some very basic details.

To work around this, you can use :class:`types.PackedChat`, which is designed to be easy to store.
This means your application can choose the best way to deal with them rather than being forced into Telethon's session.

.. seealso::

    In-depth explanation for :doc:`/concepts/sessions`.


StringSession no longer exists
------------------------------

If you need to serialize the session data to a string, you can use something like `jsonpickle <https://pypi.org/project/jsonpickle/>`_.
Or even the built-in :mod:`pickle` followed by :mod:`base64` or just :meth:`bytes.hex`.
But be aware that these approaches probably will not be compatible with additions to the :class:`~session.Session`.


TelegramClient renamed to Client
--------------------------------

You can rename it with :keyword:`as` during import if you want to use the old name.

Python allows using namespaces via packages and modules.
Therefore, the full name :class:`telethon.Client` already indicates it's from ``telethon``, so the old name was redundant.


Changes to start and client context-manager
-------------------------------------------

You can no longer ``start()`` the client.

Instead, you will need to first :meth:`~Client.connect` and then start the :meth:`~Client.interactive_login`.

In v1, the when using the client as a context-manager, ``start()`` was called.
Since that method no longer exists, it now instead only :meth:`~Client.connect` and :meth:`~Client.disconnect`.

This means you won't get annoying prompts in your terminal if the session was not authorized.
It also means you can now use the context manager even with custom login flows.

The old ``sign_in()`` method also sent the code, which was rather confusing.
Instead, you must now :meth:`~Client.request_login_code` as a separate operation.

The old ``log_out`` was also renamed to :meth:`~Client.sign_out` for consistency with :meth:`~Client.sign_in`.


No telethon.sync hack
---------------------

You can no longer ``import telethon.sync`` to have most calls wrapped in :meth:`asyncio.loop.run_until_complete` for you.
