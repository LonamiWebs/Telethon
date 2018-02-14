.. _creating-a-client:

=================
Creating a Client
=================


Before working with Telegram's API, you need to get your own API ID and hash:

1. Follow `this link <https://my.telegram.org/>`_ and login with your
   phone number.

2. Click under API Development tools.

3. A *Create new application* window will appear. Fill in your application
   details. There is no need to enter any *URL*, and only the first two
   fields (*App title* and *Short name*) can currently be changed later.

4. Click on *Create application* at the end. Remember that your
   **API hash is secret** and Telegram won't let you revoke it.
   Don't post it anywhere!

Once that's ready, the next step is to create a ``TelegramClient``.
This class will be your main interface with Telegram's API, and creating
one is very simple:

    .. code-block:: python

        from telethon import TelegramClient

        # Use your own values here
        api_id = 12345
        api_hash = '0123456789abcdef0123456789abcdef'

        client = TelegramClient('some_name', api_id, api_hash)


Note that ``'some_name'`` will be used to save your session (persistent
information such as access key and others) as ``'some_name.session'`` in
your disk. This is by default a database file using Python's ``sqlite3``.

Before using the client, you must be connected to Telegram.
Doing so is very easy:

    ``client.connect()  # Must return True, otherwise, try again``

You may or may not be authorized yet. You must be authorized
before you're able to send any request:

    ``client.is_user_authorized()  # Returns True if you can send requests``

If you're not authorized, you need to ``.sign_in()``:

    .. code-block:: python

        phone_number = '+34600000000'
        client.send_code_request(phone_number)
        myself = client.sign_in(phone_number, input('Enter code: '))
        # If .sign_in raises PhoneNumberUnoccupiedError, use .sign_up instead
        # If .sign_in raises SessionPasswordNeeded error, call .sign_in(password=...)
        # You can import both exceptions from telethon.errors.

``myself`` is your Telegram user. You can view all the information about
yourself by doing ``print(myself.stringify())``. You're now ready to use
the client as you wish! Remember that any object returned by the API has
mentioned ``.stringify()`` method, and printing these might prove useful.

As a full example:

    .. code-block:: python

        client = TelegramClient('anon', api_id, api_hash)
        assert client.connect()
        if not client.is_user_authorized():
            client.send_code_request(phone_number)
            me = client.sign_in(phone_number, input('Enter code: '))


All of this, however, can be done through a call to ``.start()``:

    .. code-block:: python

        client = TelegramClient('anon', api_id, api_hash)
        client.start()


The code shown is just what ``.start()`` will be doing behind the scenes
(with a few extra checks), so that you know how to sign in case you want
to avoid using ``input()`` (the default) for whatever reason. If no phone
or bot token is provided, you will be asked one through ``input()``. The
method also accepts a ``phone=`` and ``bot_token`` parameters.

You can use either, as both will work. Determining which
is just a matter of taste, and how much control you need.

Remember that you can get yourself at any time with ``client.get_me()``.

.. warning::
    Please note that if you fail to login around 5 times (or change the first
    parameter of the ``TelegramClient``, which is the session name) you will
    receive a ``FloodWaitError`` of around 22 hours, so be careful not to mess
    this up! This shouldn't happen if you're doing things as explained, though.

.. note::
    If you want to use a **proxy**, you have to `install PySocks`__
    (via pip or manual) and then set the appropriated parameters:

        .. code-block:: python

            import socks
            client = TelegramClient('session_id',
                api_id=12345, api_hash='0123456789abcdef0123456789abcdef',
                proxy=(socks.SOCKS5, 'localhost', 4444)
            )

    The ``proxy=`` argument should be a tuple, a list or a dict,
    consisting of parameters described `here`__.



Two Factor Authorization (2FA)
******************************

If you have Two Factor Authorization (from now on, 2FA) enabled on your
account, calling :meth:`telethon.TelegramClient.sign_in` will raise a
``SessionPasswordNeededError``. When this happens, just
:meth:`telethon.TelegramClient.sign_in` again with a ``password=``:

    .. code-block:: python

        import getpass
        from telethon.errors import SessionPasswordNeededError

        client.sign_in(phone)
        try:
            client.sign_in(code=input('Enter code: '))
        except SessionPasswordNeededError:
            client.sign_in(password=getpass.getpass())


The mentioned ``.start()`` method will handle this for you as well, but
you must set the ``password=`` parameter beforehand (it won't be asked).

If you don't have 2FA enabled, but you would like to do so through the library,
take as example the following code snippet:

    .. code-block:: python

        import os
        from hashlib import sha256
        from telethon.tl.functions import account
        from telethon.tl.types.account import PasswordInputSettings

        new_salt = client(account.GetPasswordRequest()).new_salt
        salt = new_salt + os.urandom(8)  # new random salt

        pw = 'secret'.encode('utf-8')  # type your new password here
        hint = 'hint'

        pw_salted = salt + pw + salt
        pw_hash = sha256(pw_salted).digest()

        result = client(account.UpdatePasswordSettingsRequest(
            current_password_hash=salt,
            new_settings=PasswordInputSettings(
                new_salt=salt,
                new_password_hash=pw_hash,
                hint=hint
            )
        ))

Thanks to `Issue 259 <https://github.com/LonamiWebs/Telethon/issues/259>`_
for the tip!


__ https://github.com/Anorov/PySocks#installation
__ https://github.com/Anorov/PySocks#usage-1
