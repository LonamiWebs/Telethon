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

.. note::

    It's important that the library always accesses the same session file so
    that you don't need to re-send the code over and over again. By default it
    creates the file in your working directory, but absolute paths work too.


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

.. note::

    If you send the code that Telegram sent you over the app through the
    app itself, it will expire immediately. You can still send the code
    through the app by "obfuscating" it (maybe add a magic constant, like
    ``12345``, and then subtract it to get the real code back) or any other
    technique.

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
use ``client.edit_2fa()``.
Be sure to know what you're doing when using this function and
you won't run into any problems.
Take note that if you want to set only the email/hint and leave 
the current password unchanged, you need to "redo" the 2fa.

See the examples below:

    .. code-block:: python

        from telethon.errors import EmailUnconfirmedError
        
        # Sets 2FA password for first time:
        client.edit_2fa(new_password='supersecurepassword')
        
        # Changes password:
        client.edit_2fa(current_password='supersecurepassword', 
                        new_password='changedmymind')
        
        # Clears current password (i.e. removes 2FA):
        client.edit_2fa(current_password='changedmymind', new_password=None)
        
        # Sets new password with recovery email:
        try:
            client.edit_2fa(new_password='memes and dreams', 
                            email='JohnSmith@example.com')
            # Raises error (you need to check your email to complete 2FA setup.)
        except EmailUnconfirmedError:
            # You can put email checking code here if desired.
            pass
            
        # Also take note that unless you remove 2FA or explicitly
        # give email parameter again it will keep the last used setting
        
        # Set hint after already setting password:
        client.edit_2fa(current_password='memes and dreams',
                        new_password='memes and dreams',
                        hint='It keeps you alive')

__ https://github.com/Anorov/PySocks#installation
__ https://github.com/Anorov/PySocks#usage-1
