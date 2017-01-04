Telethon
========
**Telethon** is Telegram client implementation in Python which uses the latest available API of Telegram.
The project's **core only** is based on TLSharp, a C# Telegram client implementation.

.. contents:: Table of contents

Why Telethon?
=============
.. epigraph::

  Why should I bother with Telethon? There are more mature projects already, such as
  `telegram-cli <https://github.com/vysheng/tg>`_ with even (limited) Python support. And we have the
  `official <https://github.com/telegramdesktop/tdesktop>`_ `clients <https://github.com/DrKLO/Telegram>`_!

With Telethon you don't really need to know anything before using it. Create a client with your settings.
Connect. You're ready to go.

Being written **entirely** on Python, Telethon can run as a script under any environment you wish, (yes,
`Android too <https://f-droid.org/repository/browse/?fdfilter=termux&fdid=com.termux>`_). You can schedule it,
or use it in any other script you have. Want to send a message to someone when you're available? Write a script.
Do you want check for new messages at a given time and find relevant ones? Write a script.

Hungry for more API calls which the ``TelegramClient`` class doesn't *seem* to have implemented?
Please read `Using more than just TelegramClient`_.

Obtaining your Telegram ``API ID`` and ``Hash``
===============================================
In order to use Telethon, you first need to obtain your very own API ID and Hash:

1. Follow `this link <https://my.telegram.org>`_ and login with your phone number.
2. Click under *API Development tools*.
3. A *Create new application* window will appear. Fill in your application details.
   There is no need to enter any *URL*, and only the first two fields (*App title* and *Short name*)
   can be changed later as long as I'm aware.
4. Click on *Create application* at the end.

Now that you know your ``API ID`` and ``Hash``, you can continue installing Telethon.

Installing Telethon
===================
Installing Telethon via ``pip``
-------------------------------
On a terminal, issue the following command:

.. code:: sh

  sudo -H pip install telethon

You're ready to go.

Installing Telethon manually
----------------------------

1. Install the required ``pyaes`` module: ``sudo -H pip install pyaes``
   (`GitHub <https://github.com/ricmoo/pyaes>`_, `package index <https://pypi.python.org/pypi/pyaes>`_)
2. Clone Telethon's GitHub repository: ``git clone https://github.com/LonamiWebs/Telethon.git``
3. Enter the cloned repository: ``cd Telethon``
4. Run the code generator: ``python3 telethon_generator/tl_generator.py``
5. Done!

Running Telethon
================
If you've installed Telethon via pip, launch an interactive python3 session and enter the following:

.. code:: python

  >>> from telethon import InteractiveTelegramClient
  >>> # 'sessionid' can be 'yourname'. It'll be saved as yourname.session
  >>> # Also (obviously) replace the api_id and api_hash with your values
  ...
  >>> client = InteractiveTelegramClient('sessionid', '+34600000000',
  ...     api_id=12345, api_hash='0123456789abcdef0123456789abcdef')

  ┌─────────────────────────────────────────────┐
  │               Initialization                │
  └─────────────────────────────────────────────┘
  Initializing interactive example...
  Connecting to Telegram servers...
  >>> client.run()

If, on the other hand, you've installed Telethon manually, head to the ``api/`` directory and create a
copy of the ``settings_example`` file, naming it ``settings`` (lowercase!). Then fill the file with the
corresponding values (your ``api_id``, ``api_hash`` and phone number in international format).

Then, simply run ``python3 try_telethon.py`` to start the interactive example.

Advanced uses
=============

.. _Using more than just TelegramClient:

Using more than just ``TelegramClient``
---------------------------------------
The ``TelegramClient`` class should be used to provide a quick, well-documented and simplified starting point.
It is **not** meant to be a place for *all* the available Telegram ``Request``'s, because there are simply too many.

However, this doesn't mean that you cannot ``invoke`` all the power of Telegram's API.
Whenever you need to ``invoke`` a Telegram ``Request``, all you need to do is the following:

.. code:: python

  result = client.invoke(SomeRequest(...))

You have just ``invoke``'d ``SomeRequest`` and retrieved its ``result``! That wasn't hard at all, was it?
Now you may wonder, what's the deal with *all the power of Telegram's API*? Have a look under ``tl/functions/``.
That is *everything* you can do. You have **over 200 API** ``Request``'s at your disposal.

However, we don't pretty know *how* that ``result`` looks like. Easy. ``print(str(result))`` should
give you a quick overview. Nevertheless, there may be more than a single ``result``! Let's have a look at
this seemingly innocent ``TL`` definition:

``messages.getWebPagePreview#25223e24 message:string = MessageMedia;``

Focusing on the end, we can see that the ``result`` of invoking ``GetWebPagePreviewRequest`` is ``MessageMedia``.
But how can ``MessageMedia`` exactly look like? It's time to have another look, but this time under ``tl/types/``:

.. code:: sh

  $ tree -P "message_media_*"
  .
  ├── tl
  │   └── types
  │       ├── message_media_contact.py
  │       ├── message_media_document.py
  │       ├── message_media_empty.py
  │       ├── message_media_geo.py
  │       ├── message_media_photo.py
  │       ├── message_media_unsupported.py
  │       ├── message_media_venue.py
  │       └── message_media_web_page.py

Those are *eight* different types! How do we know what exact type it is to determine its properties? A simple
``if type(result) == MessageMediaContact:`` or similar will do. Now you're ready to take advantage of
Telegram's polymorphism.

Tips for porting Telethon
-------------------------
First of all, you need to understand how the ``scheme.tl`` (``TL`` language) works. Every object
definition is written as follows:

``name#id argument_name:argument_type = CommonType``

This means that in a single line you know what the ``TLObject`` name is. You know it's unique ID, and you
know what arguments it has. It really isn't that hard to write a generator for generating code to any platform!

The generated code should also be able to *encode* the ``Request`` into bytes, so they can be sent over
the network. This isn't a big deal either, because you know how the ``TLObject``'s are made.

Once you have your own [code generator](telethon_generator/tl_generator.py), start by looking at the
`first release <https://github.com/LonamiWebs/Telethon/releases/tag/v0.1>`_ of Telethon.
The code there is simple to understand, easy to read and hence easy to port. No extra useless features.
Only the bare bones. Perfect for starting a *new implementation*.

P.S.: I may have lied a bit. The ``TL`` language is not that easy. But it's not that hard either.
You're free to sniff the ``parser/`` files and learn how to parse other more complex lines.
Or simply use that code and change the `SourceBuilder <telethon_generator/parser/source_builder.py>`_!

Notes about the code generator
------------------------------
The code generator will skip the types considered as *core types*. These types are usually included in
almost every programming language, such as boolean values or lists, and also the Telegram True flag,
which is *not* sent but rather used to determine whether that flag should be enabled or not.

Updating the ``scheme.tl``
--------------------------
Have you found a more updated version of the ``scheme.tl`` file? Those are great news! Updating is as simple
as grabbing the
`latest version <https://github.com/telegramdesktop/tdesktop/blob/dev/Telegram/SourceFiles/mtproto/scheme.tl>`_
and replacing the one you can find in this same directory by the updated one.
Don't forget to run ``python3 tl_generator.py``.

If the changes weren't too big, everything should still work the same way as it did before; but with extra features.
