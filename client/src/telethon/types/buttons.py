"""
Keyboard buttons.

This includes both the buttons returned by :attr:`telethon.types.Message.buttons`
and those you can define when using :meth:`telethon.Client.send_message`:

.. code-block:: python

    from telethon.types import buttons

    # As a user account, you can search for and click on buttons:
    for row in message.buttons:
        for button in row:
            if isinstance(button, buttons.Callback) and button.data == b'data':
                await button.click()

    # As a bot account, you can send them:
    await bot.send_message(chat, text, buttons=[
        buttons.Callback('Demo', b'data')
    ])
"""
from .._impl.client.types.buttons import (
    Callback,
    RequestGeoLocation,
    RequestPhone,
    RequestPoll,
    SwitchInline,
    Text,
    Url,
)

__all__ = [
    "Callback",
    "RequestGeoLocation",
    "RequestPhone",
    "RequestPoll",
    "SwitchInline",
    "Text",
    "Url",
]
