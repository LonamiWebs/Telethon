======================
String-based Debugging
======================

Debugging is *really* important. Telegram's API is really big and there
is a lot of things that you should know. Such as, what attributes or fields
does a result have? Well, the easiest thing to do is printing it:

.. code-block:: python

    user = await client.get_entity('Lonami')
    print(user)

That will show a huge **string** similar to the following:

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
can be. You can just search in http://tl.telethon.dev/.

Remember that you can use Python's `isinstance
<https://docs.python.org/3/library/functions.html#isinstance>`_
to check the type of something. For example:

.. code-block:: python

    from telethon import types

    if isinstance(user.status, types.UserStatusOffline):
        print(user.status.was_online)
