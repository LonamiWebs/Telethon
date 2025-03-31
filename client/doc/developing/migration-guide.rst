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
If you feel like a major change is missing, please `open an issue <https://github.com/LonamiWebs/Telethon/>`_.


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

.. note::

    Be sure to check the documentation for :data:`telethon.errors` to learn about error changes.
    Notably, errors such as ``FloodWaitError`` no longer have a ``.seconds`` field.
    Instead, every value for every error type is always ``.value``.

This was also a good opportunity to remove a lot of modules that were not supposed to public in their entirety:
``.crypto``, ``.extensions``, ``.network``, ``.custom``, ``.functions``, ``.helpers``, ``.hints``, ``.password``, ``.requestiter``, ``.sync``, ``.types``, ``.utils``.


TelegramClient renamed to Client
--------------------------------

You can rename it with :keyword:`as` during import if you want to use the old name.

Python allows using namespaces via packages and modules.
Therefore, the full name :class:`telethon.Client` already indicates it's from ``telethon``, so the old ``Telegram`` prefix was redundant.


No telethon.sync hack
---------------------

You can no longer ``import telethon.sync`` to have most calls wrapped in :meth:`asyncio.loop.run_until_complete` for you.


Raw API is now private
----------------------

v2 aims to comply with `Semantic Versioning <https://semver.org/>`_.
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
* ``tl.abcs`` contains every abstract class, the "boxed" types from Telegram.
  You can use these for your type-hinting needs.
* ``tl.types`` contains concrete instances, the "bare" types Telegram actually returns.
  You'll probably use these with :func:`isinstance` a lot.

Most custom :mod:`types` will also have a private ``_raw`` attribute with the original value from Telegram.


Raw API has a reduced feature-set
---------------------------------

The string representation is now on :meth:`object.__repr__`, not :meth:`object.__str__`.

All types use :term:`__slots__` to save space.
This means you can't add extra fields to these at runtime unless you subclass.

The ``.stringify()`` methods on all TL types no longer exists.
Instead, you can use a library like `beauty-print <https://pypi.org/project/beauty-print/>`_.

The ``.to_dict()`` method on all TL types no longer exists.
The same is true for ``.to_json()``.
Instead, you can use a library like `json-pickle <https://pypi.org/project/jsonpickle/>`_ or write your own:

.. code-block:: python

    def to_dict(obj):
        if obj is None or isinstance(obj, (bool, int, bytes, str)): return obj
        if isinstance(obj, list): return [to_dict(x) for x in obj]
        if isinstance(obj, dict): return {k: to_dict(v) for k, v in obj.items()}
        return {slot: to_dict(getattr(obj, slot)) for slot in obj.__slots__}

Lesser-known methods such as ``TLObject.pretty_format``, ``serialize_bytes``, ``serialize_datetime`` and ``from_reader`` are also gone.
The remaining methods are:

* ``Serializable.constructor_id()`` class-method, to get the integer identifier of the corresponding type constructor.
* ``Serializable.from_bytes()`` class-method, to convert serialized :class:`bytes` back into the class.
* :meth:`object.__bytes__` instance-method, to serialize the instance into :class:`bytes` the way Telegram expects.

Functions are no longer a class with attributes.
They serialize the request immediately.
This means you cannot create request instance and change it later.
Consider using :func:`functools.partial` if you want to reuse parts of a request instead.

Functions no longer have an asynchronous ``.resolve()``.
This used to let you pass usernames and have them be resolved to :tl:`InputPeer` automatically (unless it was nested).


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

The old ``log_out()`` was also renamed to :meth:`~Client.sign_out` for consistency with :meth:`~Client.sign_in`.

The old ``is_user_authorized()`` was renamed to :meth:`~Client.is_authorized` since it works for bot accounts too.


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


.. rubric:: No ``client.kick_participant()`` method.

This is not a thing in Telegram.
It was implemented by restricting and then removing the restriction.

The old ``client.edit_permissions()`` was renamed to :meth:`Client.set_participant_restrictions`.
This defines the restrictions a banned participant has applied (bans them from doing those things).
Revoking the right to view messages will kick them.
This rename should avoid confusion, as it is now clear this is not to promote users to admin status.

For administrators, ``client.edit_admin`` was renamed to :meth:`Client.set_participant_admin_rights` for consistency.

You can also use the aliases on the :class:`~types.Participant`, :meth:`types.Participant.set_restrictions` and :meth:`types.Participant.set_admin_rights`.

Note that a new method, :meth:`Client.set_chat_default_restrictions`, must now be used to set a chat's default rights.
You can also use the alias on the :class:`~types.Group`, :meth:`types.Group.set_default_restrictions`.

.. rubric:: No ``client.download_profile_photo()`` method.

You can simply use :meth:`Client.download` now.
Note that :meth:`~Client.download` no longer supports downloading contacts as ``.vcard``.

.. rubric:: No ``client.set_proxy()`` method.

Proxy support is no longer built-in.
They were never officially maintained.
This doesn't mean you can't use them.
You're now free to choose your own proxy library and pass a different connector to the :class:`Client` constructor.

This should hopefully make it clear that most connection issues when using proxies do *not* come from Telethon.

.. rubric:: No ``client.set_receive_updates`` method.

It was not working as expected.

.. rubric:: No ``client.catch_up()`` method.

You can still configure it when creating the :class:`Client`, which was the only way to make it work anyway.

.. rubric:: No ``client.action()`` method.

.. rubric:: No ``client.takeout()`` method.

.. rubric:: No ``client.qr_login()`` method.

.. rubric:: No ``client.edit_2fa()`` method.

.. rubric:: No ``client.get_stats()`` method.

.. rubric:: No ``client.edit_folder()`` method.

.. rubric:: No ``client.build_reply_markup()`` method.

.. rubric:: No ``client.list_event_handlers()`` method.

These are out of scope for the time being.
They might be re-introduced in the future if there is a burning need for them and are not difficult to maintain.
This doesn't mean you can't do these things anymore though, since the :term:`Raw API` is still available.

Telethon v2 is committed to not exposing the raw API under any public API of the ``telethon`` package.
This means any method returning data from Telegram must have a custom wrapper object and be maintained too.
Because the standards are higher, the barrier of entry for new additions and features is higher too.


Removed or renamed message properties and methods
-------------------------------------------------

Messages no longer have ``raw_text`` or ``message`` properties.

Instead, you can access the :attr:`types.Message.text`,
:attr:`~types.Message.text_markdown` or :attr:`~types.Message.text_html`.
These names aim to be consistent with ``caption_markdown`` and ``caption_html``.

In v1, messages coming from a client used that client's parse mode as some sort of "global state".
Based on the client's parse mode, v1 ``message.text`` property would return different things.
But not *all* messages did this!
Those coming from the raw API had no client, so ``text`` couldn't know how to format the message.

Overall, the old design made the parse mode be pretty hidden.
This was not very intuitive and also made it very awkward to combine multiple parse modes.

The ``forward`` property is now :attr:`~types.Message.forward_info`.
The ``forward_to`` method is now simply :meth:`~types.Message.forward`.
This makes it more consistent with the rest of message methods.

The ``is_reply``, ``reply_to_msg_id`` and ``reply_to`` properties are now :attr:`~types.Message.replied_message_id`.
The ``get_reply_message`` method is now :meth:`~types.Message.get_replied_message`.
This should make it clear that you are not getting a reply to the current message, but rather the message it replied to.

The ``to_id``, ``via_input_bot``, ``action_entities``, ``button_count`` properties are also gone.
Some were kept for backwards-compatibility, some were redundant.

The ``click`` method no longer exists in the message.
Instead, find the right :attr:`~types.Message.buttons` to click on.

The ``download`` method no longer exists in the message.
Instead, use :attr:`~types.File.download` on the message's :attr:`~types.Message.file`.

HMMMM WEB_PREVIEW VS LINK_PREVIEW... probs use link. we're previewing a link not the web


Event and filters are now separate
----------------------------------

Event types are no longer callable and do not have filters inside them.
There is no longer nested ``class Event`` inside them either.

Instead, the event type itself is what the handler will actually be called with.
Because filters are separate, there is no longer a need for v1 ``@events.register`` either.
It also means you can combine filters with ``&``, ``|`` and ``~``.

Filters are now normal functions that work with any event.
Of course, this doesn't mean all filters make sense for all events.
But you can use them in an unified manner.

Filters no longer support asynchronous operations, which removes a footgun.
This was most commonly experienced when using usernames as the ``chats`` filter in v1, and getting flood errors you couldn't handle.
In v2, you must pass a list of identifiers.
This means getting those identifiers is up to you, and you can handle it in a way that is appropriated for your application.

.. seealso::

    In-depth explanation for :doc:`/concepts/updates`.


Behaviour changes in events
---------------------------

Events produced by the client itself will now also be received as updates.
This means, for example, that your :class:`events.NewMessage` handlers will run when you use :meth:`Client.send_message`.
This is needed to properly handle updates.

In v1, there was a backwards-compatibility hack that flagged results from the client as their "own".
But in some rare cases, it was possible to still receive messages sent by the client itself in v1.
The hack has been removed so now the library will consistently deliver all updates.

``events.StopPropagation`` no longer exists.
In v1, all handlers were always called.
Now handlers are called in order until the filter for one returns :data:`True`.
The default behaviour is that handlers after that one are not called.
This behaviour can be changed with the ``check_all_handlers`` flag in :class:`Client` constructor.

``events.CallbackQuery`` has been renamed to :class:`events.ButtonCallback` and no longer also handles "inline bot callback queries".
This was a hacky workaround.

:class:`events.MessageRead` no longer triggers when the *contents* of a message are read, such as voice notes being played.

Albums in Telegram are an illusion.
There is no "album media".
There is only separate messages pretending to be a single message.

``events.Album`` was a hack that waited for a small amount of time to group messages sharing the same grouped identifier.
If you want to wait for a full album, you will need to wait yourself:

.. code-block:: python

    pending_albums = {}  # global for simplicity
    async def gather_album(event, handler):
        if pending := pending_albums.get(event.grouped_id):
            pending.append(event)
        else:
            pending_albums[event.grouped_id] = [event]
            # Wait for other events to come in. Adjust delay to your needs.
            # This will NOT work if sequential updates are enabled (spawn a task to do the rest instead).
            await asyncio.sleep(1)
            events = pending_albums.pop(grouped_id, [])
            await handler(events)

    @client.on(events.NewMessage)
    async def handler(event):
        if event.grouped_id:
            await gather_album(event, handle_album)
        else:
            await handle_message(event)

    async def handle_album(events):
        ...  # do stuff with events

    async def handle_message(event):
        ...  # do stuff with event

Note that the above code is not foolproof and will not handle more than one client.
It might be possible for album events to be delayed for more than a second.

Note that messages that do **not** belong to an album can be received in-between an album.

Overall, it's probably better if you treat albums for what they really are:
separate messages sharing a :attr:`~types.Message.grouped_id`.


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

To replace the concept of "input chats", v2 introduces :class:`types.PeerRef`.
A "peer" represents either a :class:`~types.User`, :class:`~types.Group` or :class:`~types.Channel`, much like Telegram's :tl:`Peer`.
A "peer reference" represents *just* enough information to reference that peer without relying on Telethon's cache.
This is the most efficient way to call methods like :meth:`Client.send_message` too.

The concept of "marked IDs" also no longer exists.
This means v2 no longer supports the ``-`` or ``-100`` prefixes on identifiers.
Using the raw :tl:`Peer` to wrap the identifiers is gone, too.
Instead, you're strongly encouraged to use :class:`types.PeerRef` instances.

The concepts of "entity" or "peer" are unified to :term:`peer`.
Overall, dealing with users, groups and channels should feel a lot more natural.

.. seealso::

    In-depth explanation for :doc:`/concepts/peers`.


Other methods like ``client.get_peer_id``, ``client.get_input_entity`` and ``client.get_entity`` are gone too.
While not directly related, ``client.is_bot`` is gone as well.
You can use :meth:`Client.get_me` or read it from the session instead.

The ``telethon.utils`` package is gone entirely, so methods like ``utils.resolve_id`` no longer exist either.


Session cache no longer exists
------------------------------

At least, not the way it did before.

The v1 cache that allowed you to use just chat identifiers to call methods is no longer saved to disk.

Sessions now only contain crucial information to have a working client.
This includes the server address, authorization key, update state, and some very basic details.

To work around this, you can use :class:`types.PeerRef`, which is designed to be easy to store.
This means your application can choose the best way to deal with them rather than being forced into Telethon's session.

.. seealso::

    In-depth explanation for :doc:`/concepts/sessions`.


StringSession no longer exists
------------------------------

If you need to serialize the session data to a string, you can use something like `jsonpickle <https://pypi.org/project/jsonpickle/>`_.
Or even the built-in :mod:`pickle` followed by :mod:`base64` or just :meth:`bytes.hex`.
But be aware that these approaches probably will not be compatible with additions to the :class:`~session.Session`.
