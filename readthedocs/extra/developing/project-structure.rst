=================
Project Structure
=================


Main interface
**************

The library itself is under the ``telethon/`` directory. The
``__init__.py`` file there exposes the main ``TelegramClient``, a class
that servers as a nice interface with the most commonly used methods on
Telegram such as sending messages, retrieving the message history,
handling updates, etc.

The ``TelegramClient`` inherits the ``TelegramBareClient``. The later is
basically a pruned version of the ``TelegramClient``, which knows basic
stuff like ``.invoke()``\ 'ing requests, downloading files, or switching
between data centers. This is primary to keep the method count per class
and file low and manageable.

Both clients make use of the ``network/mtproto_sender.py``. The
``MtProtoSender`` class handles packing requests with the ``salt``,
``id``, ``sequence``, etc., and also handles how to process responses
(i.e. pong, RPC errors). This class communicates through Telegram via
its ``.connection`` member.

The ``Connection`` class uses a ``extensions/tcp_client``, a C#-like
``TcpClient`` to ease working with sockets in Python. All the
``TcpClient`` know is how to connect through TCP and writing/reading
from the socket with optional cancel.

The ``Connection`` class bundles up all the connections modes and sends
and receives the messages accordingly (TCP full, obfuscated,
intermediate…).

Auto-generated code
*******************

The files under ``telethon_generator/`` are used to generate the code
that gets placed under ``telethon/tl/``. The ``TLGenerator`` takes in a
``.tl`` file, and spits out the generated classes which represent, as
Python classes, the request and types defined in the ``.tl`` file. It
also constructs an index so that they can be imported easily.
