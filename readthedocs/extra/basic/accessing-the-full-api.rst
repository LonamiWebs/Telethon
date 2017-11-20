==========================
Accessing the Full API
==========================

The ``TelegramClient`` doesn’t offer a method for every single request
the Telegram API supports. However, it’s very simple to ``.invoke()``
any request. Whenever you need something, don’t forget to `check the
documentation`__ and look for the `method you need`__. There you can go
through a sorted list of everything you can do.

You should also refer to the documentation to see what the objects
(constructors) Telegram returns look like. Every constructor inherits
from a common type, and that’s the reason for this distinction.

Say ``client.send_message()`` didn’t exist, we could use the `search`__
to look for “message”. There we would find `SendMessageRequest`__,
which we can work with.

Every request is a Python class, and has the parameters needed for you
to invoke it. You can also call ``help(request)`` for information on
what input parameters it takes. Remember to “Copy import to the
clipboard”, or your script won’t be aware of this class! Now we have:

    .. code-block:: python
    
        from telethon.tl.functions.messages import SendMessageRequest

If you’re going to use a lot of these, you may do:

    .. code-block:: python
    
        import telethon.tl.functions as tl
        # We now have access to 'tl.messages.SendMessageRequest'

We see that this request must take at least two parameters, a ``peer``
of type `InputPeer`__, and a ``message`` which is just a Python
``str``\ ing.

How can we retrieve this ``InputPeer``? We have two options. We manually
`construct one`__, for instance:

    .. code-block:: python

        from telethon.tl.types import InputPeerUser

        peer = InputPeerUser(user_id, user_hash)

Or we call ``.get_input_entity()``:

    .. code-block:: python

        peer = client.get_input_entity('someone')

When you’re going to invoke an API method, most require you to pass an
``InputUser``, ``InputChat``, or so on, this is why using
``.get_input_entity()`` is more straightforward (and sometimes
immediate, if you know the ID of the user for instance). If you also
need to have information about the whole user, use ``.get_entity()``
instead:

    .. code-block:: python

        entity = client.get_entity('someone')

In the later case, when you use the entity, the library will cast it to
its “input” version for you. If you already have the complete user and
want to cache its input version so the library doesn’t have to do this
every time its used, simply call ``.get_input_peer``:

    .. code-block:: python

        from telethon import utils
        peer = utils.get_input_user(entity)

After this small parenthesis about ``.get_entity`` versus
``.get_input_entity``, we have everything we need. To ``.invoke()`` our
request we do:

    .. code-block:: python

        result = client(SendMessageRequest(peer, 'Hello there!'))
        # __call__ is an alias for client.invoke(request). Both will work

Message sent! Of course, this is only an example.
There are nearly 250 methods available as of layer 73,
and you can use every single of them as you wish.
Remember to use the right types! To sum up:

    .. code-block:: python

        result = client(SendMessageRequest(
            client.get_input_entity('username'), 'Hello there!'
        ))


.. note::

    Note that some requests have a "hash" parameter. This is **not** your ``api_hash``!
    It likely isn't your self-user ``.access_hash`` either.
    It's a special hash used by Telegram to only send a difference of new data
    that you don't already have with that request,
    so you can leave it to 0, and it should work (which means no hash is known yet).

    For those requests having a "limit" parameter,
    you can often set it to zero to signify "return as many items as possible".
    This won't work for all of them though,
    for instance, in "messages.search" it will actually return 0 items.


__ https://lonamiwebs.github.io/Telethon
__ https://lonamiwebs.github.io/Telethon/methods/index.html
__ https://lonamiwebs.github.io/Telethon/?q=message
__ https://lonamiwebs.github.io/Telethon/methods/messages/send_message.html
__ https://lonamiwebs.github.io/Telethon/types/input_peer.html
__ https://lonamiwebs.github.io/Telethon/constructors/input_peer_user.html