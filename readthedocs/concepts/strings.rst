======================
String-based Debugging
======================

Debugging is *really* important. Telegram's API is really big and there
are a lot of things that you should know. Such as, what attributes or fields
does a result have? Well, the easiest thing to do is printing it:

.. code-block:: python

    entity = await client.get_entity('username')
    print(entity)

That will show a huge **string** similar to the following:

.. code-block:: python

    Channel(id=1066197625, title='Telegram Usernames', photo=ChatPhotoEmpty(), date=datetime.datetime(2016, 12, 16, 15, 15, 43, tzinfo=datetime.timezone.utc), version=0, creator=False, left=True, broadcast=True, verified=True, megagroup=False, restricted=False, signatures=False, min=False, scam=False, has_link=False, has_geo=False, slowmode_enabled=False, access_hash=-6309373984955162244, username='username', restriction_reason=[], admin_rights=None, banned_rights=None, default_banned_rights=None, participants_count=None)

That's a lot of text. But as you can see, all the properties are there.
So if you want the title you **don't use regex** or anything like
splitting ``str(entity)`` to get what you want. You just access the
attribute you need:

.. code-block:: python

    title = entity.title

Can we get better than the shown string, though? Yes!

.. code-block:: python

    print(entity.stringify())

Will show a much better representation:

.. code-block:: python

    Channel(
        id=1066197625,
        title='Telegram Usernames',
        photo=ChatPhotoEmpty(
        ),
        date=datetime.datetime(2016, 12, 16, 15, 15, 43, tzinfo=datetime.timezone.utc),
        version=0,
        creator=False,
        left=True,
        broadcast=True,
        verified=True,
        megagroup=False,
        restricted=False,
        signatures=False,
        min=False,
        scam=False,
        has_link=False,
        has_geo=False,
        slowmode_enabled=False,
        access_hash=-6309373984955162244,
        username='username',
        restriction_reason=[
        ],
        admin_rights=None,
        banned_rights=None,
        default_banned_rights=None,
        participants_count=None
    )


Now it's easy to see how we could get, for example,
the ``year`` value. It's inside ``date``:

.. code-block:: python

    channel_year = entity.date.year

You don't need to print everything to see what all the possible values
can be. You can just search in http://tl.telethon.dev/.

Remember that you can use Python's `isinstance
<https://docs.python.org/3/library/functions.html#isinstance>`_
to check the type of something. For example:

.. code-block:: python

    from telethon import types

    if isinstance(entity.photo, types.ChatPhotoEmpty):
        print('Channel has no photo')
