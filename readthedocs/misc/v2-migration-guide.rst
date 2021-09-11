=========================
Version 2 Migration Guide
=========================

Version 2 represents the second major version change, breaking compatibility
with old code beyond the usual raw API changes in order to clean up a lot of
the technical debt that has grown on the project.

This document documents all the things you should be aware of when migrating
from Telethon version 1.x to 2.0 onwards.


User, chat and channel identifiers are now 64-bit numbers
---------------------------------------------------------

`Layer 133 <https://diff.telethon.dev/?from=132&to=133>`__ changed *a lot* of identifiers from
``int`` to ``long``, meaning they will no longer fit in 32 bits, and instead require 64 bits.

If you were storing these identifiers somewhere size did matter (for example, a database), you
will need to migrate that to support the new size requirement of 8 bytes.

For the full list of types changed, please review the above link.


Many modules are now private
----------------------------

There were a lot of things which were public but should not have been. From now on, you should
only rely on things that are either publicly re-exported or defined. That is, as soon as anything
starts with an underscore (``_``) on its name, you're acknowledging that the functionality may
change even across minor version changes, and thus have your code break.

* The ``telethon.client`` module is now ``telethon._client``, meaning you should stop relying on
  anything inside of it. This includes all of the subclasses that used to exist (like ``UserMethods``).


Synchronous compatibility mode has been removed
-----------------------------------------------

The "sync hack" (which kicked in as soon as anything from ``telethon.sync`` was imported) has been
removed. This implies:

* The ``telethon.sync`` module is gone.
* Synchronous context-managers (``with`` as opposed to ``async with``) are no longer supported.
  Most notably, you can no longer do ``with client``. It must be ``async with client`` now.
* The "smart" behaviour of the following methods has been removed and now they no longer work in
  a synchronous context when the ``asyncio`` event loop was not running. This means they now need
  to be used with ``await`` (or, alternatively, manually used with ``loop.run_until_complete``):
  * ``start``
  * ``disconnect``
  * ``run_until_disconnected``

// TODO provide standalone alternative for this?


The Conversation API has been removed
-------------------------------------

This API had certain shortcomings, such as lacking persistence, poor interaction with other event
handlers, and overcomplicated usage for anything beyond the simplest case.

It is not difficult to write your own code to deal with a conversation's state. A simple
`Finite State Machine <https://stackoverflow.com/a/62246569/>`__ inside your handlers will do
just fine:

.. code-block:: python

    from enum import Enum, auto

    # We use a Python Enum for the state because it's a clean and easy way to do it
    class State(Enum):
        WAIT_NAME = auto()
        WAIT_AGE = auto()

    # The state in which different users are, {user_id: state}
    conversation_state = {}

    # ...code to create and setup your client...

    @client.on(events.NewMessage)
    async def handler(event):
        who = event.sender_id
        state = conversation_state.get(who)

        if state is None:
            # Starting a conversation
            await event.respond('Hi! What is your name?')
            conversation_state[who] = State.WAIT_NAME

        elif state == State.WAIT_NAME:
            name = event.text  # Save the name wherever you want
            await event.respond('Nice! What is your age?')
            conversation_state[who] = State.WAIT_AGE

        elif state == State.WAIT_AGE:
            age = event.text  # Save the age wherever you want
            await event.respond('Thank you!')
            # Conversation is done so we can forget the state of this user
            del conversation_state[who]

    # ...code to keep Telethon running...

Not only is this approach simpler, but it can also be easily persisted, and you can adjust it
to your needs and your handlers much more easily.

// TODO provide standalone alternative for this?
