.. _mastering-telethon:

==================
Mastering Telethon
==================

You've come far! In this section you will learn best practices, as well
as how to fix some silly (yet common) errors you may have found. Let's
start with a simple one.

Asyncio madness
***************

We promise ``asyncio`` is worth learning. Take your time to learn it.
It's a powerful tool that enables you to use this powerful library.
You need to be comfortable with it if you want to master Telethon.

.. code-block:: text

    AttributeError: 'coroutine' object has no attribute 'id'

You probably had a previous version, upgraded, and expected everything
to work. Remember, just add this line:

.. code-block:: python

    import telethon.sync

If you're inside an event handler you need to ``await`` **everything** that
*makes a network request*. Getting users, sending messages, and nearly
everything in the library needs access to the network, so they need to
be awaited:

.. code-block:: python

    @client.on(events.NewMessage)
    async def handler(event):
        print((await event.get_sender()).username)


You may want to read https://lonamiwebs.github.io/blog/asyncio/ to help
you understand ``asyncio`` better. I'm open for `feedback
<https://t.me/LonamiWebs>`_ regarding that blog post

Entities
********

A lot of methods and requests require *entities* to work. For example,
you send a message to an *entity*, get the username of an *entity*, and
so on. There is an entire section on this at :ref:`entities` due to their
importance.

There are a lot of things that work as entities: usernames, phone numbers,
chat links, invite links, IDs, and the types themselves. That is, you can
use any of those when you see an "entity" is needed.

You should use, **from better to worse**:

1. Input entities. For example, `event.input_chat
   <telethon.tl.custom.chatgetter.ChatGetter.input_chat>`,
   `message.input_sender
   <telethon.tl.custom.sendergetter.SenderGetter.input_sender>`,
   or caching an entity you will use a lot with
   ``entity = await client.get_input_entity(...)``.

2. Entities. For example, if you had to get someone's
   username, you can just use ``user`` or ``channel``.
   It will work. Only use this option if you already have the entity!

3. IDs. This will always look the entity up from the
   cache (the ``*.session`` file caches seen entities).

4. Usernames, phone numbers and links. The cache will be
   used too (unless you force a `client.get_entity()
   <telethon.client.users.UserMethods.get_entity>`),
   but may make a request if the username, phone or link
   has not been found yet.

In short, unlike in most bot API libraries where you use the ID, you
**should not** use the ID *if* you have the input entity. This is OK:

.. code-block:: python

    async def handler(event):
        await client.send_message(event.sender_id, 'Hi')

However, **this is better**:

.. code-block:: python

    async def handler(event):
        await client.send_message(event.input_sender, 'Hi')

Note that this also works for `message <telethon.tl.custom.message.Message>`
instead of ``event``. Telegram may not send the sender information, so if you
want to be 99% confident that the above will work you should do this:

.. code-block:: python

    async def handler(event):
        await client.send_message(await event.get_input_sender(), 'Hi')

Methods are able to make network requests to get information that
could be missing. Properties will never make a network request.

Of course, it is convenient to IDs or usernames for most purposes. It will
be fast enough and caching with `client.get_input_entity(...)
<telethon.client.users.UserMethods.get_input_entity>` will
be a micro-optimization. However it's worth knowing, and it
will also let you know if the entity cannot be found beforehand.

.. note::

    Sometimes Telegram doesn't send the access hash inside entities,
    so using `chat <telethon.tl.custom.chatgetter.ChatGetter.chat>`
    or `sender <telethon.tl.custom.sendergetter.SenderGetter.sender>`
    may not work, but `input_chat
    <telethon.tl.custom.chatgetter.ChatGetter.input_chat>`
    and `input_sender
    <telethon.tl.custom.sendergetter.SenderGetter.input_sender>`
    while making requests definitely will since that's what they exist
    for. If Telegram did not send information about the access hash,
    you will get something like "Invalid channel object" or
    "Invalid user object".


Debugging
*********

**Please enable logging**:

.. code-block:: python

    import logging
    logging.basicConfig(level=logging.WARNING)

Change it for ``logging.DEBUG`` if you are asked for logs. It will save you
a lot of headaches and time when you work with events. This is for errors.

Debugging is *really* important. Telegram's API is really big and there
is a lot of things that you should know. Such as, what attributes or fields
does a result have? Well, the easiest thing to do is printing it:

.. code-block:: python

    user = client.get_entity('Lonami')
    print(user)

That will show a huge line similar to the following:

.. code-block:: python

    User(id=10885151, is_self=False, contact=False, mutual_contact=False, deleted=False, bot=False, bot_chat_history=False, bot_nochats=False, verified=False, restricted=False, min=False, bot_inline_geo=False, access_hash=123456789012345678, first_name='Lonami', last_name=None, username='Lonami', phone=None, photo=UserProfilePhoto(photo_id=123456789012345678, photo_small=FileLocation(dc_id=4, volume_id=1234567890, local_id=1234567890, secret=123456789012345678), photo_big=FileLocation(dc_id=4, volume_id=1234567890, local_id=1234567890, secret=123456789012345678)), status=UserStatusOffline(was_online=datetime.datetime(2018, 1, 2, 3, 4, 5, tzinfo=datetime.timezone.utc)), bot_info_version=None, restriction_reason=None, bot_inline_placeholder=None, lang_code=None)

That's a lot of text. But as you can see, all the properties are there.
So if you want the username you **don't use regex** or anything like
splitting ``str(user)`` to get what you want. You just access the
attribute you need:

.. code-block:: python

    username = user.username

Can we get better than the shown string, though? Yes!

.. code-block:: python

    print(user.stringify())

Will show a much better:

.. code-block:: python

    User(
        id=10885151,
        is_self=False,
        contact=False,
        mutual_contact=False,
        deleted=False,
        bot=False,
        bot_chat_history=False,
        bot_nochats=False,
        verified=False,
        restricted=False,
        min=False,
        bot_inline_geo=False,
        access_hash=123456789012345678,
        first_name='Lonami',
        last_name=None,
        username='Lonami',
        phone=None,
        photo=UserProfilePhoto(
            photo_id=123456789012345678,
            photo_small=FileLocation(
                dc_id=4,
                volume_id=123456789,
                local_id=123456789,
                secret=-123456789012345678
            ),
            photo_big=FileLocation(
                dc_id=4,
                volume_id=123456789,
                local_id=123456789,
                secret=123456789012345678
            )
        ),
        status=UserStatusOffline(
            was_online=datetime.datetime(2018, 1, 2, 3, 4, 5, tzinfo=datetime.timezone.utc)
        ),
        bot_info_version=None,
        restriction_reason=None,
        bot_inline_placeholder=None,
        lang_code=None
    )

Now it's easy to see how we could get, for example,
the ``was_online`` time. It's inside ``status``:

.. code-block:: python

    online_at = user.status.was_online

You don't need to print everything to see what all the possible values
can be. You can just search in http://lonamiwebs.github.io/Telethon/.

Remember that you can use Python's `isinstance
<https://docs.python.org/3/library/functions.html#isinstance>`_
to check the type of something. For example:

.. code-block:: python

    from telethon import types

    if isinstance(user.status, types.UserStatusOffline):
        print(user.status.was_online)

Avoiding Limits
***************

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

Chat or User From Messages
**************************

Although it's explicitly noted in the documentation that messages
*subclass* `ChatGetter <telethon.tl.custom.chatgetter.ChatGetter>`
and `SenderGetter <telethon.tl.custom.sendergetter.SenderGetter>`,
some people still don't get inheritance.

When the documentation says "Bases: `telethon.tl.custom.chatgetter.ChatGetter`"
it means that the class you're looking at, *also* can act as the class it
bases. In this case, `ChatGetter <telethon.tl.custom.chatgetter.ChatGetter>`
knows how to get the *chat* where a thing belongs to.

So, a `Message <telethon.tl.custom.message.Message>` is a
`ChatGetter <telethon.tl.custom.chatgetter.ChatGetter>`.
That means you can do this:

.. code-block:: python

    message.is_private
    message.chat_id
    message.get_chat()
    # ...etc

`SenderGetter <telethon.tl.custom.sendergetter.SenderGetter>` is similar:

.. code-block:: python

    message.user_id
    message.get_input_user()
    message.user
    # ...etc

Quite a few things implement them, so it makes sense to reuse the code.
For example, all events (except raw updates) implement `ChatGetter
<telethon.tl.custom.chatgetter.ChatGetter>` since all events occur
in some chat.

Session Files
*************

They are an important part for the library to be efficient, such as caching
and handling your authorization key (or you would have to login every time!).

However, some people have a lot of trouble with SQLite, especially in Windows:

.. code-block:: text

    ...some lines of traceback
    'insert or replace into entities values (?,?,?,?,?)', rows)
    sqlite3.OperationalError: database is locked

This error occurs when **two or more clients use the same session**,
that is, when you write the same session name to be used in the client:

* You have two scripts running (interactive sessions count too).
* You have two clients in the same script running at the same time.

The solution is, if you need two clients, use two sessions. If the
problem persists and you're on Linux, you can use ``fuser my.session``
to find out the process locking the file. As a last resort, you can
reboot your system.

If you really dislike SQLite, use a different session storage. There
is an entire section covering that at :ref:`sessions`.

Final Words
***********

Now you are aware of some common errors and use cases, this should help
you master your Telethon skills to get the most out of the library. Have
fun developing awesome things!
