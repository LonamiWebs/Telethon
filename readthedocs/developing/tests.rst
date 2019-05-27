=====
Tests
=====

In order to test Telegram, the library makes use of the public test servers.

To run the tests, you need to provide the test runner with two environment
variables, containing the string-sessions for both a user account and a bot
account.

These accounts will talk to each other in order to run all the tests involving
high level functions.


Dependencies
============

.. code-block:: python

    pip install pytest pytest-asyncio --user


Generating Sessions
===================

First you must login with your phone number to the test servers. It is not
possible to use a public phone number because anyone could interrupt the
tests while running, and they are not allowed to create bots.

With the following code, you will authorize a new user session in the public
test servers, and also create a bot with a randomly-generated username. Once
both are created, it will print a string session of both.

.. code-block:: python

    import random
    import string

    from telethon import TelegramClient
    from telethon.sessions import StringSession

    # From https://my.telegram.org
    API   = 123, 'abc...'
    DC    = 2, '149.154.167.40', 443
    PHONE = '+34...'

    # Generate a random username for the bot account (24 chars long is good)
    bot_username = ''.join(random.choice(string.ascii_lowercase) for _ in range(21)) + 'bot'

    client = TelegramClient(StringSession(), *API)
    client.session.set_dc(*DC)

    # You will receive a SMS with the code
    with client.start(phone=PHONE):
        # Print your client session as a variable
        print('CLIENT_SESSION="{}"'.format(client.session.save()))

        # Now, create a new bot to also get a bot session
        with client.conversation('BotFather') as conv:
            conv.send_message('/newbot')
            conv.get_response()
            conv.send_message('Telethon Test Bot')
            conv.get_response()
            conv.send_message(bot_username)
            token = conv.get_response().get_entities_text(types.MessageEntityCode)[0][1]

            bot = TelegramClient(StringSession(), *API)
            bot.session.set_dc(*DC)
            with bot.start(bot_token=token):
                print('BOT_SESSION="{}"'.format(bot.session.save()))


Running the Tests
=================

Put the generated environment variables in your environment, and then run:

.. code-block:: sh

    pytest

On the root directory of the project. If everything went well, you should be
greeted with all tests passing. If they don't pass, please `open an issue`_.

.. _open an issue: https://github.com/LonamiWebs/Telethon/issues
