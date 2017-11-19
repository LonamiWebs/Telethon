=========================
Signing In
=========================

Two Factor Authorization (2FA)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If you have Two Factor Authorization (from now on, 2FA) enabled on your account, calling
:meth:`telethon.TelegramClient.sign_in` will raise a `SessionPasswordNeededError`.
When this happens, just :meth:`telethon.TelegramClient.sign_in` again with a ``password=``:

    .. code-block:: python

        import getpass
        from telethon.errors import SessionPasswordNeededError

        client.sign_in(phone)
        try:
            client.sign_in(code=input('Enter code: '))
        except SessionPasswordNeededError:
            client.sign_in(password=getpass.getpass())

Enabling 2FA
*************

If you don't have 2FA enabled, but you would like to do so through Telethon, take as example the following code snippet:

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

Thanks to `Issue 259 <https://github.com/LonamiWebs/Telethon/issues/259>`_ for the tip!

