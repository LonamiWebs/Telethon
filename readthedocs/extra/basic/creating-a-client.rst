.. _creating-a-client:

===================
Creating a Client
===================

Before working with Telegram's API, you need to get your own API ID and hash:

1. Follow `this link <https://my.telegram.org/>`_ and login with your phone number.

2. Click under API Development tools.

3. A *Create new application* window will appear. Fill in your application details.
There is no need to enter any *URL*, and only the first two fields (*App title* and *Short name*)
can be changed later as far as I'm aware.

4. Click on *Create application* at the end. Remember that your **API hash is secret**
and Telegram won't let you revoke it. Don't post it anywhere!

Once that's ready, the next step is to create a ``TelegramClient``.
This class will be your main interface with Telegram's API, and creating one is very simple:

    .. code-block:: python

        from telethon import TelegramClient

        # Use your own values here
        api_id = 12345
        api_hash = '0123456789abcdef0123456789abcdef'
        phone_number = '+34600000000'

        client = TelegramClient('some_name', api_id, api_hash)

Note that ``'some_name'`` will be used to save your session (persistent information such as access key and others)
as ``'some_name.session'`` in your disk. This is simply a JSON file which you can (but shouldn't) modify.

Before using the client, you must be connected to Telegram. Doing so is very easy:

    ``client.connect()  # Must return True, otherwise, try again``

You may or may not be authorized yet. You must be authorized before you're able to send any request:

    ``client.is_user_authorized()  # Returns True if you can send requests``

If you're not authorized, you need to ``.sign_in()``:

    .. code-block:: python

        client.send_code_request(phone_number)
        myself = client.sign_in(phone_number, input('Enter code: '))
        # If .sign_in raises PhoneNumberUnoccupiedError, use .sign_up instead
        # If .sign_in raises SessionPasswordNeeded error, call .sign_in(password=...)
        # You can import both exceptions from telethon.errors.

``myself`` is your Telegram user.
You can view all the information about yourself by doing ``print(myself.stringify())``.
You're now ready to use the client as you wish!

.. note::
    If you want to use a **proxy**, you have to `install PySocks`__ (via pip or manual)
    and then set the appropriated parameters:

        .. code-block:: python

            import socks
            client = TelegramClient('session_id',
                api_id=12345, api_hash='0123456789abcdef0123456789abcdef',
                proxy=(socks.SOCKS5, 'localhost', 4444)
            )

    The ``proxy=`` argument should be a tuple, a list or a dict,
    consisting of parameters described `here`__.


__ https://github.com/Anorov/PySocks#installation
__ https://github.com/Anorov/PySocks#usage-1%3E