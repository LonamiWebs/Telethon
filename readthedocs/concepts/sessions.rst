.. _sessions:

==============
Session Files
==============

.. contents::

They are an important part for the library to be efficient, such as caching
and handling your authorization key (or you would have to login every time!).

What are Sessions?
==================

The first parameter you pass to the constructor of the
:ref:`TelegramClient <telethon-client>` is
the ``session``, and defaults to be the session name (or full path). That is,
if you create a ``TelegramClient('anon')`` instance and connect, an
``anon.session`` file will be created in the working directory.

Note that if you pass a string it will be a file in the current working
directory, although you can also pass absolute paths.

The session file contains enough information for you to login without
re-sending the code, so if you have to enter the code more than once,
maybe you're changing the working directory, renaming or removing the
file, or using random names.

These database files using ``sqlite3`` contain the required information to
talk to the Telegram servers, such as to which IP the client should connect,
port, authorization key so that messages can be encrypted, and so on.

These files will by default also save all the input entities that you've seen,
so that you can get information about a user or channel by just their ID.
Telegram will **not** send their ``access_hash`` required to retrieve more
information about them, if it thinks you have already seem them. For this
reason, the library needs to store this information offline.

The library will by default too save all the entities (chats and channels
with their name and username, and users with the phone too) in the session
file, so that you can quickly access them by username or phone number.

If you're not going to work with updates, or don't need to cache the
``access_hash`` associated with the entities' ID, you can disable this
by setting ``client.session.save_entities = False``.


Different Session Storage
=========================

If you don't want to use the default SQLite session storage, you can also
use one of the other implementations or implement your own storage.

While it's often not the case, it's possible that SQLite is slow enough to
be noticeable, in which case you can also use a different storage. Note that
this is rare and most people won't have this issue, but it's worth a mention.

To use a custom session storage, simply pass the custom session instance to
:ref:`TelegramClient <telethon-client>` instead of
the session name.

Telethon contains three implementations of the abstract ``Session`` class:

.. currentmodule:: telethon.sessions

* `MemorySession <memory.MemorySession>`: stores session data within memory.
* `SQLiteSession <sqlite.SQLiteSession>`: stores sessions within on-disk SQLite databases. Default.
* `StringSession <string.StringSession>`: stores session data within memory,
  but can be saved as a string.

You can import these ``from telethon.sessions``. For example, using the
`StringSession <string.StringSession>` is done as follows:

.. code-block:: python

    from telethon.sync import TelegramClient
    from telethon.sessions import StringSession

    with TelegramClient(StringSession(string), api_id, api_hash) as client:
        ...  # use the client

        # Save the string session as a string; you should decide how
        # you want to save this information (over a socket, remote
        # database, print it and then paste the string in the code,
        # etc.); the advantage is that you don't need to save it
        # on the current disk as a separate file, and can be reused
        # anywhere else once you log in.
        string = client.session.save()

    # Note that it's also possible to save any other session type
    # as a string by using ``StringSession.save(session_instance)``:
    client = TelegramClient('sqlite-session', api_id, api_hash)
    string = StringSession.save(client.session)

There are other community-maintained implementations available:

* `SQLAlchemy <https://github.com/tulir/telethon-session-sqlalchemy>`_:
  stores all sessions in a single database via SQLAlchemy.

* `Redis <https://github.com/ezdev128/telethon-session-redis>`_:
  stores all sessions in a single Redis data store.

* `MongoDB <https://github.com/watzon/telethon-session-mongo>`_:
  stores the current session in a MongoDB database.


Creating your Own Storage
=========================

The easiest way to create your own storage implementation is to use
`MemorySession <memory.MemorySession>` as the base and check out how
`SQLiteSession <sqlite.SQLiteSession>` or one of the community-maintained
implementations work. You can find the relevant Python files under the
``sessions/`` directory in the Telethon's repository.

After you have made your own implementation, you can add it to the
community-maintained session implementation list above with a pull request.


String Sessions
===============

`StringSession <string.StringSession>` are a convenient way to embed your
login credentials directly into your code for extremely easy portability,
since all they take is a string to be able to login without asking for your
phone and code (or faster start if you're using a bot token).

The easiest way to generate a string session is as follows:

.. code-block:: python

    from telethon.sync import TelegramClient
    from telethon.sessions import StringSession

    with TelegramClient(StringSession(), api_id, api_hash) as client:
        print(client.session.save())


Think of this as a way to export your authorization key (what's needed
to login into your account). This will print a string in the standard
output (likely your terminal).

.. warning::

    **Keep this string safe!** Anyone with this string can use it
    to login into your account and do anything they want to.

    This is similar to leaking your ``*.session`` files online,
    but it is easier to leak a string than it is to leak a file.


Once you have the string (which is a bit long), load it into your script
somehow. You can use a normal text file and ``open(...).read()`` it or
you can save it in a variable directly:

.. code-block:: python

    string = '1aaNk8EX-YRfwoRsebUkugFvht6DUPi_Q25UOCzOAqzc...'
    with TelegramClient(StringSession(string), api_id, api_hash) as client:
        client.loop.run_until_complete(client.send_message('me', 'Hi'))


These strings are really convenient for using in places like Heroku since
their ephemeral filesystem will delete external files once your application
is over.
