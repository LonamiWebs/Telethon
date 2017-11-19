

*****************
Examples
*****************

Prelude
---------

Before reading any specific example, make sure to read the following common steps:

All the examples assume that you have successfully created a client and you're authorized as follows:

    .. code-block:: python

        from telethon import TelegramClient

        # Use your own values here
        api_id = 12345
        api_hash = '0123456789abcdef0123456789abcdef'
        phone_number = '+34600000000'

        client = TelegramClient('some_name', api_id, api_hash)
        client.connect()  # Must return True, otherwise, try again

        if not client.is_user_authorized():
            client.send_code_request(phone_number)
            # .sign_in() may raise PhoneNumberUnoccupiedError
            # In that case, you need to call .sign_up() to get a new account
            client.sign_in(phone_number, input('Enter code: '))

        # The `client´ is now ready

Although Python will probably clean up the resources used by the ``TelegramClient``,
you should always ``.disconnect()`` it once you're done:

    .. code-block:: python

        try:
            # Code using the client goes here
        except:
            # No matter what happens, always disconnect in the end
            client.disconnect()

If the examples aren't enough, you're strongly advised to read the source code
for the InteractiveTelegramClient_ for an overview on how you could build your next script.
This example shows a basic usage more than enough in most cases. Even reading the source
for the TelegramClient_ may help a lot!


Signing In
--------------

.. toctree::
    examples-signing-in


Working with messages
-----------------------

.. toctree::
    examples-working-with-messages


.. _InteractiveTelegramClient: https://github.com/LonamiWebs/Telethon/blob/master/telethon_examples/interactive_telegram_client.py
.. _TelegramClient: https://github.com/LonamiWebs/Telethon/blob/master/telethon/telegram_client.py
