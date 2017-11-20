.. _sessions:

==============
Session Files
==============

The first parameter you pass the the constructor of the
``TelegramClient`` is the ``session``, and defaults to be the session
name (or full path). That is, if you create a ``TelegramClient('anon')``
instance and connect, an ``anon.session`` file will be created on the
working directory.

These JSON session files contain the required information to talk to the
Telegram servers, such as to which IP the client should connect, port,
authorization key so that messages can be encrypted, and so on.

These files will by default also save all the input entities that you’ve
seen, so that you can get information about an user or channel by just
their ID. Telegram will **not** send their ``access_hash`` required to
retrieve more information about them, if it thinks you have already seem
them. For this reason, the library needs to store this information
offline.

The library will by default too save all the entities (users with their
name, username, chats and so on) **in memory**, not to disk, so that you
can quickly access them by username or phone number. This can be
disabled too. Run ``help(client.session.entities)`` to see the available
methods (or ``help(EntityDatabase)``).

If you’re not going to work without updates, or don’t need to cache the
``access_hash`` associated with the entities’ ID, you can disable this
by setting ``client.session.save_entities = False``.

If you don’t want to save the files as JSON, you can also create your
custom ``Session`` subclass and override the ``.save()`` and ``.load()``
methods. For example, you could save it on a database:

    .. code-block:: python

        class DatabaseSession(Session):
            def save():
                # serialize relevant data to the database

            def load():
                # load relevant data to the database

You should read the ``session.py`` source file to know what “relevant
data” you need to keep track of.