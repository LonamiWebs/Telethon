Signing in
==========

.. currentmodule:: telethon

Most of Telegram's API methods are gated behind an account login.
But before you can interact with the API at all, you will need to obtain an API ID and hash pair for your application.


Registering your Telegram application
-------------------------------------

Before working with Telegram's API, you (as the application developer) need to get an API ID and hash:

1.  `Login to your Telegram account <https://my.telegram.org/>`_ with the phone number of the developer account to use.

2.  Click under *API Development tools*.

3.  A *Create new application* window will appear. Fill in your application details.
    There is no need to enter any *URL*, and only the first two fields (*App title* and *Short name*) can currently be changed later.

4.  Click on *Create application* at the end.
    Remember that your **API hash is secret** and Telegram won't let you revoke it.
    Don't post it anywhere!

This API ID and hash can now be used to develop an application using Telegram's API.
Telethon consumes this API ID and hash in order to make the requests to Telegram.

It is important to note that this API ID and hash is attached to a developer account,
and can be used to develop applications or otherwise using libraries such as Telethon.

The *users* of the application you develop do *not* need to provide their own API ID and hash.
The API ID and hash values are meant to be hardcoded in the application.
Any user is then able to login with just their phone number or bot token, even if they have not registered an application themselves.

.. important::

    The API ID and hash are meant to be *secret*, but Python is often distributed in source-code form.
    These two things conflict with eachother!
    You can opt to obfuscate the values somehow, or perhaps distribute an executable binary file instead.
    Depending on what you are developing, it might be reasonable to expect users to provide their own API ID and hash instead.

    Official applications *also* must embed the API ID and hash, but these are often distributed as binary files.
    Whatever you do, **do not use other people's API ID and hash!**
    Telegram may detect this as suspicious and ban the accounts.

If you receive an error, Telegram is likely blocking the registration of a new applications.
The best you can do is wait and try again later.
If the issue persists, you may try contacting them, using a proxy or using a VPN.
Be aware that some phone numbers are not eligible to register applications with.


Interactive login
-----------------

The library offers a method for "quick and dirty" scripts known as :meth:`~Client.interactive_login`.
This method will first check whether the account was previously logged-in, and if not, ask for a phone number to be input.

You can write the code in a file (such as ``hello.py``) and then run it, or use the built-in ``asyncio``-enabled REPL.
For this tutorial, we'll be using the ``asyncio`` REPL:

.. code-block:: shell

    python -m asyncio

.. important::

    If you opt to write your code in a file, do **not** call your script ``telethon.py``!
    Python will try to import from there and it will fail with an error such as "ImportError: cannot import name ...".

The first thing we need to do is import the :class:`Client` class and create an instance of it:

.. code-block:: python

    from telethon import Client

    client = Client('name', 12345, '0123456789abcdef0123456789abcdef')

The second and third parameters must be the API ID and hash, respectively.
We have a client instance now, but we can't send requests to Telegram until we connect!
So the next step is to :meth:`~Client.connect`:

.. code-block:: python

    await client.connect()

If all went well, you will have connected to one of Telegram's servers.
If you run into issues, you might need to try a different hosting provider or use some sort of proxy.

Once you're connected, we can begin the :meth:`~Client.interactive_login`:

.. code-block:: python

    await client.interactive_login()

Do as the prompts say on the terminal, and you will have successfully logged-in!

Once you're done, make sure to :meth:`~Client.disconnect` for a graceful shutdown.


Manual login
------------

We've talked about the second and third parameters of the :class:`Client` constructor, but not the first:

.. code-block:: python

    client = Client('name', 12345, '0123456789abcdef0123456789abcdef')

The first parameter is the "session".
When using a string or a :class:`~pathlib.Path`, the library will create a SQLite database in that path.
The session path can contain directory separators and live anywhere in the file system.
Telethon will automatically append the ``.session`` extension if you don't provide any.

Briefly, the session contains some of the information needed to connect to Telegram.
This includes the datacenter belonging to the account logged-in, and the authorization key used for encryption, among other things.

.. important::

    **Do not leak the session file!**
    Anyone with that file can login to the account stored in it.
    If you believe someone else has obtained this file, immediately revoke all active sessions from an official client.

Let's take a look at what :meth:`~Client.interactive_login` does under the hood.

1. First, it's using an equivalent of :meth:`~Client.is_authorized` to check whether the session was logged-in previously.
2. Then, it will either :meth:`~Client.bot_sign_in` with a bot token or :meth:`~Client.request_login_code` with a phone number.

    * If it logged-in as a bot account, a :class:`~types.User` is returned and we're done.
    * Otherwise, a login code was sent. Go to step 3.

3. Attempt to complete the user sign-in with :meth:`~Client.sign_in`, by entering the login code.

    * If a :class:`~types.User` is returned, we're done.
    * Otherwise, a 2FA password is required. Go to step 4.

4. Use :meth:`Client.check_password` to check that the password is correct.

    * If the password is correct, :class:`~types.User` is returned and we're done.

Put into code, a user can thus login as follows:

.. code-block:: python

    from telethon import Client
    from telethon.types import User

    # SESSION, API_ID, API_HASH should be previously defined in your code
    async with Client(SESSION, API_ID, API_HASH) as client:
        if not await client.is_authorized():
            phone = input('phone: ')
            login_token = await client.request_login_code(phone_or_token)

        code = input('code: ')
        user_or_token = await client.sign_in(login_token, code)

        if isinstance(user_or_token, User):
            return user_or_token

        # user_or_token is PasswordToken
        password_token = user_or_token

        import getpass
        password = getpass.getpass("password: ")
        user = await client.check_password(password_token, password)
        return user

A bot account does not need to request login code and cannot have passwords, so the login flow is much simpler:

.. code-block:: python

    from telethon import Client

    # SESSION, API_ID, API_HASH should be previously defined in your code
    async with Client(SESSION, API_ID, API_HASH) as client:
        bot_token = input('token: ')
        bot_user = await client.bot_sign_in(bot_token)
        return bot_user

To get a bot account, you need to talk with `@BotFather <https://t.me/BotFather>`_.

You may have noticed the ``async with`` keywords.
The :class:`Client` can be used in a context-manager.
This will automatically call :meth:`Client.connect` and :meth:`Client.disconnect` for you.

A good way to structure your code is as follows:

.. code-block:: python

    import asyncio
    from telethon import Client

    SESSION = ...
    API_ID = ...
    API_HASH = ...

    async def main():
        async with Client(SESSION, API_ID, API_HASH) as client:
            ...  # use client to your heart's content

    if __name__ == '__main__':
        asyncio.run(main())

This way, both the :mod:`asyncio` event loop and the :class:`Client` will exit cleanly.
Otherwise, you might run into errors such as tasks being destroyed while pending.

.. note::

    Once a :class:`Client` instance has been connected, you cannot change the :mod:`asyncio` event loop.
    Methods like :func:`asyncio.run` setup and tear-down a new event loop every time.
    If the loop changes, the client is likely to be "stuck" because its loop cannot advance.
