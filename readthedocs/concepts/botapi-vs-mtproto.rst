.. _botapi:

=======================
HTTP Bot API vs MTProto
=======================


Telethon is more than just another viable alternative when developing bots
for Telegram. If you haven't decided which wrapper library for bots to use
yet, using Telethon from the beginning may save you some headaches later.

.. contents::


What is Bot API?
================

The `Telegram Bot API`_, also known as HTTP Bot API and from now on referred
to as simply "Bot API" is Telegram's official way for developers to control
their own Telegram bots. Quoting their main page:

    The Bot API is an HTTP-based interface created for developers keen on
    building bots for Telegram.

    To learn how to create and set up a bot, please consult our
    `Introduction to Bots`_ and `Bot FAQ`_.

Bot API is simply an HTTP endpoint which translates your requests to it into
MTProto calls through tdlib_, their bot backend.


What is MTProto?
================

MTProto_ is Telegram's own protocol to communicate with their API when you
connect to their servers.

Telethon is an alternative MTProto-based backend written entirely in Python
and much easier to setup and use.

Both official applications and third-party clients (like your own
applications) logged in as either user or bots **can use MTProto** to
communicate directly with Telegram's API (which is not the HTTP bot API).

When we talk about MTProto, we often mean "MTProto-based clients".


Advantages of MTProto over Bot API
==================================

MTProto clients (like Telethon) connect directly to Telegram's servers,
which means there is no HTTP connection, no "polling" or "web hooks". This
means **less overhead**, since the protocol used between you and the server
is much more compact than HTTP requests with responses in wasteful JSON.

Since there is a direct connection to Telegram's servers, even if their
Bot API endpoint is down, you can still have connection to Telegram directly.

Using a MTProto client, you are also not limited to the public API that
they expose, and instead, **you have full control** of what your bot can do.
Telethon offers you all the power with often **much easier usage** than any
of the available Python Bot API wrappers.

If your application ever needs user features because bots cannot do certain
things, you will be able to easily login as a user and even keep your bot
without having to learn a new library.

If less overhead and full control didn't convince you to use Telethon yet,
check out the wiki page `MTProto vs HTTP Bot API`_ with a more exhaustive
and up-to-date list of differences.


Migrating from Bot API to Telethon
==================================

It doesn't matter if you wrote your bot with requests_ and you were
making API requests manually, or if you used a wrapper library like
python-telegram-bot_ or pyTelegramBotAPI_. It's never too late to
migrate to Telethon!

If you were using an asynchronous library like aiohttp_ or a wrapper like
aiogram_ or dumbot_, it will be even easier, because Telethon is also an
asynchronous library.

Next, we will see some examples from the most popular libraries.


Migrating from python-telegram-bot
----------------------------------

Let's take their `echobot.py`_ example and shorten it a bit:

.. code-block:: python

    from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

    def start(update, context):
        """Send a message when the command /start is issued."""
        update.message.reply_text('Hi!')

    def echo(update, context):
        """Echo the user message."""
        update.message.reply_text(update.message.text)

    def main():
        """Start the bot."""
        updater = Updater("TOKEN")
        dp = updater.dispatcher
        dp.add_handler(CommandHandler("start", start))
        dp.add_handler(MessageHandler(Filters.text & ~Filters.command, echo))

        updater.start_polling()

        updater.idle()

    if __name__ == '__main__':
        main()


After using Telethon:

.. code-block:: python

    from telethon import TelegramClient, events

    bot = TelegramClient('bot', 11111, 'a1b2c3d4').start(bot_token='TOKEN')

    @bot.on(events.NewMessage(pattern='/start'))
    async def start(event):
        """Send a message when the command /start is issued."""
        await event.respond('Hi!')
        raise events.StopPropagation

    @bot.on(events.NewMessage)
    async def echo(event):
        """Echo the user message."""
        await event.respond(event.text)

    def main():
        """Start the bot."""
        bot.run_until_disconnected()

    if __name__ == '__main__':
        main()

Key differences:

* The recommended way to do it imports fewer things.
* All handlers trigger by default, so we need ``events.StopPropagation``.
* Adding handlers, responding and running is a lot less verbose.
* Telethon needs ``async def`` and ``await``.
* The ``bot`` isn't hidden away by ``Updater`` or ``Dispatcher``.


Migrating from pyTelegramBotAPI
-------------------------------

Let's show another echobot from their README:

.. code-block:: python

    import telebot

    bot = telebot.TeleBot("TOKEN")

    @bot.message_handler(commands=['start'])
    def send_welcome(message):
        bot.reply_to(message, "Howdy, how are you doing?")

    @bot.message_handler(func=lambda m: True)
    def echo_all(message):
        bot.reply_to(message, message.text)

    bot.polling()

Now we rewrite it to use Telethon:

.. code-block:: python

    from telethon import TelegramClient, events

    bot = TelegramClient('bot', 11111, 'a1b2c3d4').start(bot_token='TOKEN')

    @bot.on(events.NewMessage(pattern='/start'))
    async def send_welcome(event):
        await event.reply('Howdy, how are you doing?')

    @bot.on(events.NewMessage)
    async def echo_all(event):
        await event.reply(event.text)

    bot.run_until_disconnected()

Key differences:

* Instead of doing ``bot.reply_to(message)``, we can do ``event.reply``.
  Note that the ``event`` behaves just like their ``message``.
* Telethon also supports ``func=lambda m: True``, but it's not necessary.


Migrating from aiogram
----------------------

From their GitHub:

.. code-block:: python

    from aiogram import Bot, Dispatcher, executor, types

    API_TOKEN = 'BOT TOKEN HERE'

    # Initialize bot and dispatcher
    bot = Bot(token=API_TOKEN)
    dp = Dispatcher(bot)

    @dp.message_handler(commands=['start'])
    async def send_welcome(message: types.Message):
        """
        This handler will be called when client send `/start` command.
        """
        await message.reply("Hi!\nI'm EchoBot!\nPowered by aiogram.")

    @dp.message_handler(regexp='(^cat[s]?$|puss)')
    async def cats(message: types.Message):
        with open('data/cats.jpg', 'rb') as photo:
            await bot.send_photo(message.chat.id, photo, caption='Cats is here 😺',
                                 reply_to_message_id=message.message_id)

    @dp.message_handler()
    async def echo(message: types.Message):
        await bot.send_message(message.chat.id, message.text)

    if __name__ == '__main__':
        executor.start_polling(dp, skip_updates=True)


After rewrite:

.. code-block:: python

    from telethon import TelegramClient, events

    # Initialize bot and... just the bot!
    bot = TelegramClient('bot', 11111, 'a1b2c3d4').start(bot_token='TOKEN')

    @bot.on(events.NewMessage(pattern='/start'))
    async def send_welcome(event):
        await event.reply('Howdy, how are you doing?')

    @bot.on(events.NewMessage(pattern='(^cat[s]?$|puss)'))
    async def cats(event):
        await event.reply('Cats is here 😺', file='data/cats.jpg')

    @bot.on(events.NewMessage)
    async def echo_all(event):
        await event.reply(event.text)

    if __name__ == '__main__':
        bot.run_until_disconnected()


Key differences:

* Telethon offers convenience methods to avoid retyping
  ``bot.send_photo(message.chat.id, ...)`` all the time,
  and instead let you type ``event.reply``.
* Sending files is **a lot** easier. The methods for sending
  photos, documents, audios, etc. are all the same!

Migrating from dumbot
---------------------

Showcasing their subclassing example:

.. code-block:: python

    from dumbot import Bot

    class Subbot(Bot):
        async def init(self):
            self.me = await self.getMe()

        async def on_update(self, update):
            await self.sendMessage(
                chat_id=update.message.chat.id,
                text='i am {}'.format(self.me.username)
            )

    Subbot(token).run()

After rewriting:

.. code-block:: python

    from telethon import TelegramClient, events

    class Subbot(TelegramClient):
        def __init__(self, *a, **kw):
            await super().__init__(*a, **kw)
            self.add_event_handler(self.on_update, events.NewMessage)

        async def connect():
            await super().connect()
            self.me = await self.get_me()

        async def on_update(event):
            await event.reply('i am {}'.format(self.me.username))

    bot = Subbot('bot', 11111, 'a1b2c3d4').start(bot_token='TOKEN')
    bot.run_until_disconnected()


Key differences:

* Telethon method names are ``snake_case``.
* dumbot does not offer friendly methods like ``update.reply``.
* Telethon does not have an implicit ``on_update`` handler, so
  we need to manually register one.


.. _Telegram Bot API: https://core.telegram.org/bots/api
.. _Introduction to Bots: https://core.telegram.org/bots
.. _Bot FAQ: https://core.telegram.org/bots/faq
.. _tdlib: https://core.telegram.org/tdlib
.. _MTProto: https://core.telegram.org/mtproto
.. _MTProto vs HTTP Bot API: https://github.com/LonamiWebs/Telethon/wiki/MTProto-vs-HTTP-Bot-API
.. _requests: https://pypi.org/project/requests/
.. _python-telegram-bot: https://python-telegram-bot.readthedocs.io
.. _pyTelegramBotAPI: https://github.com/eternnoir/pyTelegramBotAPI
.. _aiohttp: https://docs.aiohttp.org/en/stable
.. _aiogram: https://aiogram.readthedocs.io
.. _dumbot: https://github.com/Lonami/dumbot
.. _echobot.py: https://github.com/python-telegram-bot/python-telegram-bot/blob/master/examples/echobot.py
