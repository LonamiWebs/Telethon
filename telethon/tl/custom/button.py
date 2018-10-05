from .. import types
from .messagebutton import MessageButton


class Button:
    """
    .. note::

        This class is used to **define** reply markups, e.g. when
        sending a message or replying to events. When you access
        `Message.buttons <telethon.tl.custom.message.Message.buttons>`
        they are actually `MessageButton
        <telethon.tl.custom.messagebutton.MessageButton>`,
        so you might want to refer to that class instead.

    Helper class to allow defining ``reply_markup`` when
    sending a message with inline or keyboard buttons.

    You should make use of the defined class methods to create button
    instances instead making them yourself (i.e. don't do ``Button(...)``
    but instead use methods line `Button.inline(...) <inline>` etc.

    You can use `inline`, `switch_inline` and `url`
    together to create inline buttons (under the message).

    You can use `text`, `request_location` and `request_phone`
    together to create a reply markup (replaces the user keyboard).

    You **cannot** mix the two type of buttons together,
    and it will error if you try to do so.

    The text for all buttons may be at most 142 characters.
    If more characters are given, Telegram will cut the text
    to 128 characters and add the ellipsis (…) character as
    the 129.
    """
    def __init__(self):
        raise ValueError('Cannot create instances of this class; '
                         'use the static methods')

    @staticmethod
    def _is_inline(button):
        """
        Returns ``True`` if the button belongs to an inline keyboard.
        """
        return isinstance(button, (
            types.KeyboardButtonCallback,
            types.KeyboardButtonSwitchInline,
            types.KeyboardButtonUrl
        ))

    @staticmethod
    def inline(text, data=None):
        """
        Creates a new inline button.

        If `data` is omitted, the given `text` will be used as `data`.
        In any case `data` should be either ``bytes`` or ``str``.

        Note that the given `data` must be less or equal to 64 bytes.
        If more than 64 bytes are passed as data, ``ValueError`` is raised.
        """
        if not data:
            data = text.encode('utf-8')
        elif not isinstance(data, (bytes, bytearray, memoryview)):
            data = str(data).encode('utf-8')

        if len(data) > 64:
            raise ValueError('Too many bytes for the data')

        return types.KeyboardButtonCallback(text, data)

    @staticmethod
    def switch_inline(text, query='', same_peer=False):
        """
        Creates a new button to switch to inline query.

        If `query` is given, it will be the default text to be used
        when making the inline query.

        If ``same_peer is True`` the inline query will directly be
        set under the currently opened chat. Otherwise, the user will
        have to select a different dialog to make the query.
        """
        return types.KeyboardButtonSwitchInline(text, query, same_peer)

    @staticmethod
    def url(text, url=None):
        """
        Creates a new button to open the desired URL upon clicking it.

        If no `url` is given, the `text` will be used as said URL instead.
        """
        return types.KeyboardButtonUrl(text, url or text)

    @staticmethod
    def text(text):
        """
        Creates a new button with the given text.
        """
        return types.KeyboardButton(text)

    @staticmethod
    def request_location(text):
        """
        Creates a new button that will request
        the user's location upon being clicked.
        """
        return types.KeyboardButtonRequestGeoLocation(text)

    @staticmethod
    def request_phone(text):
        """
        Creates a new button that will request
        the user's phone number upon being clicked.
        """
        return types.KeyboardButtonRequestPhone(text)

    @staticmethod
    def clear():
        """
        Clears all the buttons. When used, no other
        button should be present or it will be ignored.
        """
        return types.ReplyKeyboardHide()

    @staticmethod
    def force_reply():
        """
        Forces a reply. If used, no other button
        should be present or it will be ignored.
        """
        return types.ReplyKeyboardForceReply()
