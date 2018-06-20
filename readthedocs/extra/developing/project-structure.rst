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

The ``TelegramClient`` inherits from several mixing ``Method`` classes,
since there are so many methods that having them in a single file would
make maintenance painful (it was three thousand lines before this separation
happened!). It's a "god object", but there is only a way to interact with
Telegram really.

The ``TelegramBaseClient`` is an ABC which will support all of these mixins
so they can work together nicely. It doesn't even know how to invoke things
because they need to be resolved with user information first (to work with
input entities comfortably).

The client makes use of the ``network/mtprotosender.py``. The
``MTProtoSender`` is responsible for connecting, reconnecting,
packing, unpacking, sending and receiving items from the network.
Basically, the low-level communication with Telegram, and handling
MTProto-related functions and types such as ``BadSalt``.

The sender makes use of a ``Connection`` class which knows the format in
which outgoing messages should be sent (how to encode their length and
their body, if they're further encrypted).

For now, all connection modes make use of the ``extensions/tcpclient``,
a C#-like ``TcpClient`` to ease working with sockets in Python. All the
``TcpClient`` know is how to connect through TCP and writing/reading
from the socket with optional cancel.

Auto-generated code
*******************

The files under ``telethon_generator/`` are used to generate the code
that gets placed under ``telethon/tl/``. The parsers take in files in
a specific format (such as ``.tl`` for objects and ``.json`` for errors)
and spit out the generated classes which represent, as Python classes,
the request and types defined in the ``.tl`` file. It also constructs
an index so that they can be imported easily.

Custom documentation can also be generated to easily navigate through
the vast amount of items offered by the API.
