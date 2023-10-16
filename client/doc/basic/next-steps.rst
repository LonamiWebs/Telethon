Next steps
==========

.. currentmodule:: telethon

By now, you should have successfully gone through both the :doc:`installation` and :doc:`signing-in` processes.

With a :class:`Client` instance connected and authorized, you can send any request to Telegram.
Some requests are bot-specific, and some are user-specific, but most can be used by any account.
You will need to have the correct permissions and pass valid parameters, but after that, your imagination is the limit.

Telethon features extensive documentation for every public item offered by the library.
All methods within the :class:`Client` also contain one or more examples on how to use them.

Whatever you build, remember to comply with both `Telegram's Terms of Service <https://telegram.org/tos>`_
and `Telegram's API ToS <https://core.telegram.org/api/terms>`_.
There are `several requests that applications must make <https://core.telegram.org/api/config#terms-of-service>`_:

.. epigraph::

    […] when logging in as an existing user, apps are supposed to call :tl:`help.getTermsOfServiceUpdate`
    to check for any updates to the Terms of Service;
    this call should be repeated after ``expires`` seconds have elapsed.
    If an update to the Terms Of Service is available, clients are supposed to show a consent popup;
    if accepted, clients should call :tl:`help.acceptTermsOfService`,
    providing the ``termsOfService id`` JSON object;
    in case of denial, clients are to delete the account using :tl:`account.deleteAccount`,
    providing Decline ToS update as deletion reason.

The library will not make these calls for you, as it cannot know how users interact with the application being developed.
If you use an official client alongside the application you are developing,
it should be safe to rely on that client making the requests instead.

Having your account banned might sound scary.
However, keep in mind that people often don't post comments when things work fine!
The only comments you're likely to see are negative ones.
As long as you use a real phone number and don't abuse the API, you will most likely be fine.
This library would not be used at all otherwise!

If you believe your account was banned on accident,
`there are ways to try to get it back <https://github.com/LonamiWebs/Telethon/issues/824>`_.

If you are using a bot account instead, the risk of a ban is either zero or very close to it.
If you know of a bot causing account bans, please let me know so it can be documented.
