.. _sessions:

==============
Session Files
==============

The first parameter you pass to the constructor of the ``TelegramClient`` is
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
so that you can get information about an user or channel by just their ID.
Telegram will **not** send their ``access_hash`` required to retrieve more
information about them, if it thinks you have already seem them. For this
reason, the library needs to store this information offline.

The library will by default too save all the entities (chats and channels
with their name and username, and users with the phone too) in the session
file, so that you can quickly access them by username or phone number.

If you're not going to work with updates, or don't need to cache the
``access_hash`` associated with the entities' ID, you can disable this
by setting ``client.session.save_entities = False``.

Custom Session Storage
----------------------

If you don't want to use the default SQLite session storage, you can also use
one of the other implementations or implement your own storage.

To use a custom session storage, simply pass the custom session instance to
``TelegramClient`` instead of the session name.

Telethon contains two implementations of the abstract ``Session`` class:

* ``MemorySession``: stores session data in Python variables.
* ``SQLiteSession``, (default): stores sessions in their own SQLite databases.

There are other community-maintained implementations available:

* `SQLAlchemy <https://github.com/tulir/telethon-session-sqlalchemy>`_: stores all sessions in a single database via SQLAlchemy.
* `Redis <https://github.com/ezdev128/telethon-session-redis>`_: stores all sessions in a single Redis data store.

Creating your own storage
~~~~~~~~~~~~~~~~~~~~~~~~~

The easiest way to create your own storage implementation is to use ``MemorySession``
as the base and check out how ``SQLiteSession`` or one of the community-maintained
implementations work. You can find the relevant Python files under the ``sessions``
directory in Telethon.

After you have made your own implementation, you can add it to the community-maintained
session implementation list above with a pull request.

SQLite Sessions and Heroku
--------------------------

You probably have a newer version of SQLite installed (>= 3.8.2). Heroku uses
SQLite 3.7.9 which does not support ``WITHOUT ROWID``. So, if you generated
your session file on a system with SQLite >= 3.8.2 your session file will not
work on Heroku's platform and will throw a corrupted schema error.

There are multiple ways to solve this, the easiest of which is generating a
session file on your Heroku dyno itself. The most complicated is creating
a custom buildpack to install SQLite >= 3.8.2.


Generating a SQLite Session File on a Heroku Dyno
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. note::
    Due to Heroku's ephemeral filesystem all dynamically generated
    files not part of your applications buildpack or codebase are destroyed
    upon each restart.

.. warning::
    Do not restart your application Dyno at any point prior to retrieving your
    session file. Constantly creating new session files from Telegram's API
    will result in a 24 hour rate limit ban.

Due to Heroku's ephemeral filesystem all dynamically generated
files not part of your applications buildpack or codebase are destroyed upon
each restart.

Using this scaffolded code we can start the authentication process:

    .. code-block:: python

        client = TelegramClient('login.session', api_id, api_hash).start()

At this point your Dyno will crash because you cannot access stdin. Open your
Dyno's control panel on the Heroku website and "Run console" from the "More"
dropdown at the top right. Enter ``bash`` and wait for it to load.

You will automatically be placed into your applications working directory.
So run your application ``python app.py`` and now you can complete the input
requests such as "what is your phone number" etc.

Once you're successfully authenticated exit your application script with
CTRL + C and ``ls`` to confirm ``login.session`` exists in your current
directory. Now you can create a git repo on your account and commit
``login.session`` to that repo.

You cannot ``ssh`` into your Dyno instance because it has crashed, so unless
you programatically upload this file to a server host this is the only way to
get it off of your Dyno.

You now have a session file compatible with SQLite <= 3.8.2. Now you can
programatically fetch this file from an external host (Firebase, S3 etc.)
and login to your session using the following scaffolded code:

    .. code-block:: python

        fileName, headers = urllib.request.urlretrieve(file_url, 'login.session')
        client = TelegramClient(os.path.abspath(fileName), api_id, api_hash).start()

.. note::
    - ``urlretrieve`` will be depreciated, consider using ``requests``.
    - ``file_url`` represents the location of your file.
