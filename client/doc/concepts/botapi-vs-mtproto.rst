HTTP Bot API vs MTProto
=======================

.. currentmodule:: telethon

Telethon is more than capable to develop bots for Telegram.
If you haven't decided which wrapper library for bots to use yet,
using Telethon from the beginning may save you some headaches later.


What is Bot API?
----------------

`Telegram's HTTP Bot API <https://core.telegram.org/bots/api>`_,
from now on referred to as simply "Bot API", is Telegram's official way for developers to control their own Telegram bots.
Quoting their main page:

.. epigraph::

    The :term:`Bot API` is an HTTP-based interface created for developers keen on building bots for Telegram.

    To learn how to create and set up a bot, please consult our
    `Introduction to Bots <https://core.telegram.org/bots>`_
    and `Bot FAQ <https://core.telegram.org/bots/faq>`_.

:term:`Bot API` is simply an HTTP endpoint offering a custom HTTP API.
Underneath, it uses `tdlib <https://core.telegram.org/tdlib>`_ to talk to Telegram's servers.

You can configure your bot details via `@BotFather <https://t.me/BotFather>`_.
This includes name, commands, and auto-completion.


What is MTProto?
----------------

`MTProto <https://core.telegram.org/mtproto>`_ stands for "Mobile Transport Protocol".
It is the language that the Telegram servers "speak".
You can think of it as an alternative to HTTP.

Telegram offers multiple APIs.
All user accounts must use the API offered via MTProto.
We will call this API the "MTProto API".
This is the canonical Telegram API.

The MTProto API is different from Bot API, but bot accounts can use either in the same way.
In fact, the Bot API is implemented to use the MTProto API to map the requests and responses.

Telethon implements the MTProto and offers classes and methods that can be called to send requests.
In Telethon, all the methods and types generated from Telegram's API definitions are also known as :term:`Raw API`.
This name was chosen because it gives you "raw" access to the MTProto API.
Telethon's :class:`Client` and other custom types are implemented using the :term:`Raw API`.


Why is an API ID and hash needed for bots with MTProto?
-------------------------------------------------------

When talking to Telegram's API directly, you need an API ID and hash to sign in to their servers.
API access is forbidden without an API ID, and the sign in can only be done with the API hash.

When using the :term:`Bot API`, that layer talks to the MTProto API underneath.
To do so, it uses its own private API ID and hash.

When you cut on the intermediary, you need to provide your own.
In a similar manner, the authorization key which remembers that you logged-in must be kept locally.


Advantages of MTProto over Bot API
----------------------------------

MTProto clients (like Telethon) connect directly to Telegram's servers via TCP or UDP.
There is no HTTP connection, no "polling", and no "web hooks".
We can compare the two visually:

.. graphviz::
    :caption: Communication between a Client and the Bot API

    digraph botapi {
        rankdir=LR;
        "Client" -> "HTTP API";
        "HTTP API" -> "MTProto API";
        "MTProto API" -> "Telegram Servers";

        "Telegram Servers" -> "MTProto API" [label="IPC"];
        "MTProto API" -> "HTTP API" [label="MTProto"];
        "HTTP API" -> "Client" [label="JSON"];
    }

.. graphviz::
    :caption: Communication between a Client and the MTProto API

    digraph botapi {
        rankdir=LR;
        "Client" -> "MTProto API";
        "MTProto API" -> "Telegram Servers";

        "Telegram Servers" -> "MTProto API" [label="IPC"];
        "MTProto API" -> "Client" [label="MTProto"];
    }

When interacting with the MTProto API directly, we can cut down one intermediary (the HTTP API).
This is less theoretical overhead and latency.
It also means that, even if the Bot API endpoint is down, talking to the MTProto API could still work.

The methods offered by the Bot API map to some of the methods in the MTProto API, but not all.
The Bot API is its own abstraction, and chooses to expose less details.
By talking to the MTProto API directly, you unlock the `full potential <https://github.com/LonamiWebs/Telethon/wiki/MTProto-vs-HTTP-Bot-API>`_.

The serialization format used by MTProto is more compact than JSON and can still be compressed.

Another benefit of avoiding the Bot API is the ease to switch to user accounts instead of bots.
The MTProto API is the same for users and bots, so by using Telethon, you don't need to learn to use a second library.


Migrating from Bot API to Telethon
----------------------------------

If the above points convinced you to switch to Telethon, the following short guides should help you make the switch!

It doesn't matter if you wrote your bot with `requests <https://pypi.org/project/requests/>`_
and you were making API requests manually, or if you used a wrapper library like
`python-telegram-bot <https://python-telegram-bot.readthedocs.io>`_
or `pyTelegramBotAPI <https://pytba.readthedocs.io/en/latest/index.html>`.
You will surely be pleased with Telethon!

If you were using an asynchronous library like `aiohttp <https://docs.aiohttp.org/en/stable/>`_
or a wrapper like `aiogram <https://docs.aiogram.dev/en/latest/>`_, the switch will be even easier.


Migrating from PTB v13.x
^^^^^^^^^^^^^^^^^^^^^^^^

Using one of the examples from their v13 wiki with the ``.ext`` module:

.. code-block:: python

    from telegram import Update
    from telegram.ext import Updater, CallbackContext, CommandHandler

    updater = Updater(token='TOKEN', use_context=True)
    dispatcher = updater.dispatcher

    def start(update: Update, context: CallbackContext):
        context.bot.send_message(chat_id=update.effective_chat.id, text="I'm a bot, please talk to me!")

    start_handler = CommandHandler('start', start)
    dispatcher.add_handler(start_handler)

    updater.start_polling()

The code creates an ``Updater`` instance.
This will take care of polling updates for the bot associated with the given token.
Then, a ``CommandHandler`` using our ``start`` function is added to the dispatcher.
At the end, we block, telling the updater to do its job.

In Telethon:

.. code-block:: python

    import asyncio
    from telethon import Client
    from telethon.events import NewMessage, filters

    updater = Client('bot', api_id, api_hash)

    async def start(update: NewMessage):
        await update.client.send_message(chat=update.chat.id, text="I'm a bot, please talk to me!")

    start_filter = filters.Command('/start')
    updater.add_event_handler(start, NewMessage, start_filter)

    async def main():
        async with updater:
            await updater.interactive_login('TOKEN')
            await updater.run_until_disconnected()

    asyncio.run(main())

Key differences:

* Telethon only has a :class:`~telethon.Client`, not separate ``Bot`` or ``Updater`` classes.
* There is no separate dispatcher. The :class:`~telethon.Client` is capable of dispatching updates.
* Telethon handlers only have one parameter, the event.
* There is no context, but the :attr:`~telethon.events.Event.client` property exists in all events.
* Handler types are :mod:`~telethon.events.filters` and don't have a ``Handler`` suffix.
* Telethon must define the update type (:class:`~telethon.events.NewMessage`) and filter.
* The setup to run the client (and dispatch updates) is a bit more involved with :mod:`asyncio`.

Here's the above code in idiomatic Telethon:

.. code-block:: python

    import asyncio
    from telethon import Client, events
    from telethon.events import filters

    client = Client('bot', api_id, api_hash)

    @client.on(events.NewMessage, filters.Command('/start'))
    async def start(event):
        await event.respond("I'm a bot, please talk to me!")

    async def main():
        async with client:
            await client.interactive_login('TOKEN')
            await client.run_until_disconnected()

    asyncio.run(main())

Events can be added using decorators and methods such as :meth:`types.Message.respond` help reduce the verbosity.


Migrating from PTB v20.x
^^^^^^^^^^^^^^^^^^^^^^^^

Using one of the examples from their v13 wiki with the ``.ext`` module:

.. code-block:: python

    from telegram import Update
    from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler

    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await context.bot.send_message(chat_id=update.effective_chat.id, text="I'm a bot, please talk to me!")

    if __name__ == '__main__':
        application = ApplicationBuilder().token('TOKEN').build()

        start_handler = CommandHandler('start', start)
        application.add_handler(start_handler)

        application.run_polling()

No need to import the :mod:`asyncio` module directly!
Now instead there are builders to help set stuff up.

In Telethon:

.. code-block:: python

    import asyncio
    from telethon import Client
    from telethon.events import NewMessage, filters

    async def start(update: NewMessage):
        await update.client.send_message(chat=update.chat.id, text="I'm a bot, please talk to me!")

    async def main():
        application = Client('bot', api_id, api_hash)

        start_filter = filters.Command('/start')
        application.add_event_handler(start, NewMessage, start_filter)

        async with application:
            await application.interactive_login('TOKEN')
            await application.run_until_disconnected()

    asyncio.run(main())

Key differences:

* No builders. Telethon tries to get out of your way on how you structure your code.
* The client must be connected before it can run, hence the ``async with``.

Here's the above code in idiomatic Telethon:

.. code-block:: python

    import asyncio
    from telethon import Client, events
    from telethon.events import filters

    @client.on(events.NewMessage, filters.Command('/start'))
    async def start(event):
        await event.respond("I'm a bot, please talk to me!")

    async def main():
        async with Client('bot', api_id, api_hash) as client:
            await client.interactive_login('TOKEN')
            client.add_event_handler(start, NewMessage, filters.Command('/start'))
            await client.run_until_disconnected()

    asyncio.run(main())

Note how the client can be created and started in the same line.
This makes it easy to have clean disconnections once the script exits.


Migrating from asynchronous TeleBot
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Using one of the examples from their v4 pyTelegramBotAPI documentation:

.. code-block:: python

    from telebot.async_telebot import AsyncTeleBot
    bot = AsyncTeleBot('TOKEN')

    # Handle '/start' and '/help'
    @bot.message_handler(commands=['help', 'start'])
    async def send_welcome(message):
        await bot.reply_to(message, """\
    Hi there, I am EchoBot.
    I am here to echo your kind words back to you. Just say anything nice and I'll say the exact same thing to you!\
    """)

    # Handle all other messages with content_type 'text' (content_types defaults to ['text'])
    @bot.message_handler(func=lambda message: True)
    async def echo_message(message):
        await bot.reply_to(message, message.text)

    import asyncio
    asyncio.run(bot.polling())

This showcases a command handler and a catch-all echo handler, both added with decorators.

In Telethon:

.. code-block:: python

    from telethon import Client, events
    from telethon.events.filters import Any, Command, TextOnly
    bot = Client('bot', api_id, api_hash)

    # Handle '/start' and '/help'
    @bot.on(events.NewMessage, Any(Command('/help'), Command('/start')))
    async def send_welcome(message: NewMessage):
        await message.reply("""\
    Hi there, I am EchoBot.
    I am here to echo your kind words back to you. Just say anything nice and I'll say the exact same thing to you!\
    """)

    # Handle all other messages with only 'text'
    @bot.on(events.NewMessage, TextOnly())
    async def echo_message(message: NewMessage):
        await message.reply(message.text)

    import asyncio
    async def main():
        async with bot:
            await bot.interactive_login('TOKEN')
            await bot.run_until_disconnected()
    asyncio.run(main())

Key differences:

* The handler type is defined using the event type instead of being a specific method in the client.
* Filters are also separate instances instead of being tied to specific event types.
* The ``reply_to`` helper is in the message, not the client instance.
* Setup is a bit more involved because the connection is not implicit.

For the most part, it's a 1-to-1 translation and the result is idiomatic Telethon.


Migrating from aiogram
^^^^^^^^^^^^^^^^^^^^^^

Using one of the examples from their v3 documentation with logging and comments removed:

.. code-block:: python

    import asyncio

    from aiogram import Bot, Dispatcher, types
    from aiogram.enums import ParseMode
    from aiogram.filters import CommandStart
    from aiogram.types import Message
    from aiogram.utils.markdown import hbold

    dp = Dispatcher()

    @dp.message(CommandStart())
    async def command_start_handler(message: Message) -> None:
        await message.answer(f"Hello, {hbold(message.from_user.full_name)}!")

    @dp.message()
    async def echo_handler(message: types.Message) -> None:
        try:
            await message.send_copy(chat_id=message.chat.id)
        except TypeError:
            await message.answer("Nice try!")

    async def main() -> None:
        bot = Bot(TOKEN, parse_mode=ParseMode.HTML)
        await dp.start_polling(bot)

    if __name__ == "__main__":
        asyncio.run(main())

We can see a specific handler for the ``/start`` command and a catch-all echo handler:

In Telethon:

.. code-block:: python

    import asyncio, html

    from telethon import Client, RpcError, types, events
    from telethon.events.filters import Command
    from telethon.types import Message

    client = Client("bot", api_id, api_hash)

    @client.on(events.NewMessage, Command("/start"))
    async def command_start_handler(message: Message) -> None:
        await message.respond(html=f"Hello, <b>{html.escape(message.sender.full_name)}</b>!")

    @dp.message()
    async def echo_handler(message: types.Message) -> None:
        try:
            await message.respond(message)
        except RpcError:
            await message.respond("Nice try!")

    async def main() -> None:
        async with bot:
            await bot.interactive_login(TOKEN)
            await bot.run_until_disconnected()

    if __name__ == "__main__":
        asyncio.run(main())

Key differences:

* There is no separate dispatcher. Handlers are added to the client.
* There is no specific handler for the ``/start`` command.
* The ``answer`` method is for callback queries. Messages have :meth:`~types.Message.respond`.
* Telethon doesn't have functions to format messages. Instead, markdown or HTML are used.
* Telethon cannot have a default parse mode. Instead, it should be specified when responding.
* Telethon doesn't have ``send_copy``. Instead, :meth:`Client.send_message` accepts :class:`~types.Message`.
* If sending a message fails, the error will be :class:`RpcError`, because it comes from Telegram.
