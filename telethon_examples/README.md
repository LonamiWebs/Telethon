# Examples

This folder contains several single-file examples using [Telethon].

## Requisites

You should have the `telethon` library installed with `pip`.
Run `python3 -m pip install --upgrade telethon --user` if you don't
have it installed yet (this is the most portable way to install it).

The scripts will ask you for your API ID, hash, etc. through standard input.
You can also define the following environment variables to avoid doing so:

* `TG_API_ID`, this is your API ID from https://my.telegram.org.
* `TG_API_HASH`, this is your API hash from https://my.telegram.org.
* `TG_TOKEN`, this is your bot token from [@BotFather] for bot examples.
* `TG_SESSION`, this is the name of the `*.session` file to use.

## Downloading Examples

You may download all and run any example by typing in a terminal:
```sh
git clone https://github.com/LonamiWebs/Telethon.git
cd Telethon
cd telethon_examples
python3 gui.py
```

You can also right-click the title of any example and use "Save Link As…" to
download only a particular example.

All examples are licensed under the [CC0 License], so you can use
them as the base for your own code without worrying about copyright.

## Available Examples

### [`print_updates.py`]

* Usable as: **user and bot**.
* Difficulty: **easy**.

Trivial example that just prints all the updates Telegram originally
sends. Your terminal should support UTF-8, or Python may fail to print
some characters on screen.

### [`print_messages.py`]

* Usable as: **user and bot**.
* Difficulty: **easy**.

This example uses the different `@client.on` syntax to register event
handlers, and uses the `pattern=` variable to filter only some messages.

There are a lot other things you can do, but you should refer to the
documentation of [`events.NewMessage`] since this is only a simple example.

### [`replier.py`]

* Usable as: **user and bot**.
* Difficulty: **easy**.

This example showcases a third way to add event handlers (using decorators
but without the client; you should use the one you prefer) and will also
reply to some messages with different reactions, or to your commands.

It also shows how to enable `logging`, which you should always do, but was
not really needed for the previous two trivial examples.

### [`assistant.py`]

* Usable as a: **bot**.
* Difficulty: **medium**.

This example is the core of the actual bot account [@TelethonianBot] running
in the [official Telethon's chat] to help people out. It showcases how to
create an extremely simple "plugins" system with Telethon, but you're free
to borrow ideas from it and make it as fancy as you like (perhaps you want
to add hot reloading?).

The plugins are a separate Python file each which get loaded dynamically and
can be found at <https://github.com/Lonami/TelethonianBotExt>. To use them,
clone the repository into a `plugins` folder next to `assistant.py` and then
run `assistant.py`.

The content of the plugins or how they work is not really relevant. You can
disable them by moving them elsewhere or deleting the file entirely. The point
is to learn how you can build fancy things with your own code and Telethon.

### [`interactive_telegram_client.py`]

* Usable as: **user**.
* Difficulty: **medium**.

Interactive terminal client that you can use to list your dialogs,
send messages, delete them, and download media. The code is a bit
long which may make it harder to follow, and requires saving some
state in order for downloads to work later.

### [`quart_login.py`]

* Usable as: **user**.
* Difficulty: **medium**.

Web-based application using [Quart](https://pgjones.gitlab.io/quart/index.html)
(an `asyncio` alternative to [Flask](http://flask.pocoo.org/)) and Telethon
together.

The example should work as a base for Quart applications *with a single
global client*, and it should be easy to adapt for multiple clients by
following the comments in the code.

It showcases how to login manually (ask for phone, code, and login),
and once the user is logged in, some messages and photos will be shown
in the page.

There is nothing special about Quart. It was chosen because it's a
drop-in replacement for Flask, the most popular option for web-apps.
You can use any `asyncio` library with Telethon just as well,
like [Sanic](https://sanic.readthedocs.io/en/latest/index.html) or
[aiohttp](https://docs.aiohttp.org/en/stable/). You can even use Flask,
if you learn how to use `threading` and `asyncio` together.

### [`gui.py`]

* Usable as: **user and bot**.
* Difficulty: **high**.

This is a simple GUI written with [`tkinter`] which becomes more complicated
when there's a need to use [`asyncio`] (although it's only a bit of additional
setup). The code to deal with the interface and the commands the GUI supports
also complicate the code further and require knowledge and careful reading.

This example is the actual bot account [@TelethonianBot] running in the
[official Telethon's chat] to help people out. The file is a bit big and
assumes some [`asyncio`] knowledge, but otherwise is easy to follow.

![Screenshot of the tkinter GUI][tkinter GUI]

### [`payment.py`](https://raw.githubusercontent.com/LonamiWebs/Telethon/v1/telethon_examples/payment.py)

* Usable as: **bot**.
* Difficulty: **medium**.

This example shows how to make invoices (Telegram's way of requesting payments) via a bot account. The example does not include how to add shipping information, though.

You'll need to obtain a "provider token" to use this example, so please read [Telegram's guide on payments](https://core.telegram.org/bots/payments) before using this example.


It makes use of the ["raw API"](https://tl.telethon.dev) (that is, no friendly `client.` methods), which can be helpful in understanding how it works and how it can be used.


[Telethon]: https://github.com/LonamiWebs/Telethon
[CC0 License]: https://github.com/LonamiWebs/Telethon/blob/v1/telethon_examples/LICENSE
[@BotFather]: https://t.me/BotFather
[`assistant.py`]: https://raw.githubusercontent.com/LonamiWebs/Telethon/v1/telethon_examples/assistant.py
[`quart_login.py`]: https://raw.githubusercontent.com/LonamiWebs/Telethon/v1/telethon_examples/quart_login.py
[`gui.py`]: https://raw.githubusercontent.com/LonamiWebs/Telethon/v1/telethon_examples/gui.py
[`interactive_telegram_client.py`]: https://raw.githubusercontent.com/LonamiWebs/Telethon/v1/telethon_examples/interactive_telegram_client.py
[`print_messages.py`]: https://raw.githubusercontent.com/LonamiWebs/Telethon/v1/telethon_examples/print_messages.py
[`print_updates.py`]: https://raw.githubusercontent.com/LonamiWebs/Telethon/v1/telethon_examples/print_updates.py
[`replier.py`]: https://raw.githubusercontent.com/LonamiWebs/Telethon/v1/telethon_examples/replier.py
[@TelethonianBot]: https://t.me/TelethonianBot
[official Telethon's chat]: https://t.me/TelethonChat
[`asyncio`]: https://docs.python.org/3/library/asyncio.html
[`tkinter`]: https://docs.python.org/3/library/tkinter.html
[tkinter GUI]: https://raw.githubusercontent.com/LonamiWebs/Telethon/v1/telethon_examples/screenshot-gui.jpg
[`events.NewMessage`]: https://docs.telethon.dev/en/stable/modules/events.html#telethon.events.newmessage.NewMessage
