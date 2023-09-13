Sessions
========

.. currentmodule:: telethon

In Telethon, the word :term:`session` is used to refer to the set of data needed to connect to Telegram.
This includes the server address of your home datacenter, as well as the authorization key bound to an account.
When you first connect to Telegram, an authorization key is generated to encrypt all communication.
After login, Telegram remembers this authorization key as logged-in, so you don't need to login again.

.. important::

    **Do not leak the session file!**
    Anyone with that file can login to the account stored in it.
    If you believe someone else has obtained this file, immediately revoke all active sessions from an official client.

Some auxiliary information such as the user ID of the logged-in user is also kept.

The update state, which can change every time an update is received from Telegram, is also stored in the session.
Telethon needs this information to catch up on all missed updates while your code was not running.
This is why it's important to call :meth:`Client.disconnect`.
Doing so flushes all the update state to the session and saves it.


Session files
-------------

Telethon defaults to using SQLite to store the session state.
The session state is written to ``.session`` files, so make sure your VCS ignores them!
To make sure the ``.session`` file is saved, you should call :meth:`Client.disconnect` before exiting the program.

The first parameter in the :class:`Client` constructor is the session to use.
You can use a `str`, a :class:`pathlib.Path` or a :class:`session.Storage`.
The string or path are relative to the Current Working Directory.
You can use absolute paths or relative paths to folders elsewhere.
The ``.session`` extension is automatically added if the path has no extension.


Session storages
----------------

The :class:`session.Storage` abstract base class defines the required methods to create custom storages.
Telethon comes with two built-in storages:

* :class:`~session.SqliteSession`. This is used by default when a string or path is used.
* :class:`~session.MemorySession`. This is used by default when the path is ``None``.
  You can also use it directly when you have a :class:`~session.Session` instance.
  It's useful when you don't have file-system access.

If you would like to store the session state in a different way, you can subclass :class:`session.Storage`.

Some Python installations do not have the ``sqlite3`` module.
In this case, attempting to use the default :class:`~session.SqliteSession` will fail.
If this happens, you can try reinstalling Python.
If you still don't have the ``sqlite3`` module, you should use a different storage.
