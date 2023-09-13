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

    The Bot API is an HTTP-based interface created for developers keen on building bots for Telegram.

    To learn how to create and set up a bot, please consult our
    `Introduction to Bots <https://core.telegram.org/bots>`_
    and `Bot FAQ <https://core.telegram.org/bots/faq>`_.

Bot API is simply an HTTP endpoint offering a custom HTTP API.
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

If you were using an asynchronous library like `aiohttp <https://docs.aiohttp.org/en/stable>`_
or a wrapper like `aiogram <https://docs.aiohttp.org/en/stable>`_, the switch will be even easier.


Migrating from TODO
^^^^^^^^^^^^^^^^^^^
