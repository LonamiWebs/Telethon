Glossary
========

.. currentmodule:: telethon

.. glossary::
    :sorted:

    chat
        A :class:`~types.User`, :class:`~types.Group` or :class:`~types.Channel`.

        .. seealso:: The :doc:`../concepts/chats` concept.

    Raw API
        Functions and types under ``telethon._tl`` that enable access to all of Telegram's API.

        .. seealso:: The :doc:`../concepts/full-api` concept.

    access hash
        Account-bound integer tied to a specific resource.
        Users, channels, photos and documents are all resources with an access hash.
        The access hash doesn't change, but every account will see a different value for the same resource.

    RPC
        Remote Procedure Call.
        Invoked when calling a :class:`Client` with a function from ``telethon._tl.functions``.

    RPC Error
        Error type returned by Telegram.
        :class:`RpcError` contains an integer code similar to HTTP status codes and a name.

        .. seealso:: The :doc:`../concepts/errors` concept.

    session
        Data used to securely connect to Telegram and other state related to the logged-in account.

        .. seealso:: The :doc:`../concepts/sessions` concept.

    MTProto
        Mobile Transport Protocol used to interact with Telegram's API.

        .. seealso:: The :doc:`../concepts/botapi-vs-mtproto` concept.
