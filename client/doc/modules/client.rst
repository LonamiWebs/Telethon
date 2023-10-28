.. currentmodule:: telethon

Client class
============

The :class:`Client` class is the "entry point" of the library.

Most client methods have an alias in the respective types.
For example, :meth:`Client.forward_messages` can also be invoked from :meth:`types.Message.forward`.
With a few exceptions, "client.verb_object" methods also exist as "object.verb".

.. autoclass:: Client
