Glossary
========

.. currentmodule:: telethon

.. glossary::
    :sorted:

    chat
        A :class:`~types.User`, :class:`~types.Group` or :class:`~types.Channel`.

        .. seealso:: The :doc:`../concepts/chats` concept.

    yourself
        The logged-in account, whether that represents a bot or a user with a phone number.

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

    login
        Used to refer to the login process as a whole, as opposed to the action to :term:`sign in`.
        The "login code" or "login token" get their name because they belong to the login process.

    sign in
        Used to refer to the action to sign into either a user or bot account, as opposed to the :term:`login` process.
        Likewise, "sign out" is used to signify that the authorization should stop being valid.

    layer
        When Telegram releases new features, it does so by releasing a new "layer".
        The different layers let Telegram know what a client is capable of and how it should respond to requests.

    TL
    Type Language
        File format used by Telegram to define all the types and requests available in a :term:`layer`.
        Telegram's site has an `Overview of the TL language <https://core.telegram.org/mtproto/TL>`_.
