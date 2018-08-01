from .. import types


class Button:
    """
    Helper class to allow defining ``reply_markup`` when
    sending a message with inline or keyboard buttons.

    You should make use of the defined class methods to create button
    instances instead making them yourself (i.e. don't do ``Button(...)``
    but instead use methods line `Button.inline(...) <inline>` etc.)

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
    def __init__(self, button, callback=None):
        self.button = button
        self.callback = callback
        self.is_inline = self._is_inline(button)

    @property
    def data(self):
        if isinstance(self.button, types.KeyboardButtonCallback):
            return self.button.data

    @classmethod
    def _is_inline(cls, button):
        """
        Returns ``True`` if the button belongs to an inline keyboard.
        """
        if isinstance(button, cls):
            return button.is_inline
        else:
            return isinstance(button, (
                types.KeyboardButtonCallback,
                types.KeyboardButtonSwitchInline,
                types.KeyboardButtonUrl
            ))

    @classmethod
    def inline(cls, text, callback=None, data=None):
        """
        Creates a new inline button.

        The `callback` parameter should be a function callback accepting
        a single parameter (the triggered event on click) if specified.
        Otherwise, you should register the event manually.

        If `data` is omitted, the given `text` will be used as `data`.
        In any case `data` should be either ``bytes`` or ``str``.

        Note that the given `data` must be less or equal to 64 bytes.
        If more than 64 bytes are passed as data, ``ValueError`` is raised.
        """
        if not data:
            data = text.encode('utf-8')

        if len(data) > 64:
            raise ValueError('Too many bytes for the data')

        return cls(types.KeyboardButtonCallback(text, data), callback)

    @classmethod
    def switch_inline(cls, text, query='', same_peer=False):
        """
        Creates a new button to switch to inline query.

        If `query` is given, it will be the default text to be used
        when making the inline query.

        If ``same_peer is True`` the inline query will directly be
        set under the currently opened chat. Otherwise, the user will
        have to select a different dialog to make the query.
        """
        return cls(types.KeyboardButtonSwitchInline(text, query, same_peer))

    @classmethod
    def url(cls, text, url=None):
        """
        Creates a new button to open the desired URL upon clicking it.

        If no `url` is given, the `text` will be used as said URL instead.
        """
        return cls(types.KeyboardButtonUrl(text, url or text))

    @classmethod
    def text(cls, text):
        """
        Creates a new button with the given text.
        """
        return cls(types.KeyboardButton(text))

    @classmethod
    def request_location(cls, text):
        """
        Creates a new button that will request
        the user's location upon being clicked.
        """
        return cls(types.KeyboardButtonRequestGeoLocation(text))

    @classmethod
    def request_phone(cls, text):
        """
        Creates a new button that will request
        the user's phone number upon being clicked.
        """
        return cls(types.KeyboardButtonRequestPhone(text))

    @classmethod
    def clear(cls):
        """
        Clears all the buttons. When used, no other
        button should be present or it will be ignored.
        """
        return types.ReplyKeyboardHide()

    @classmethod
    def force_reply(cls):
        """
        Forces a reply. If used, no other button
        should be present or it will be ignored.
        """
        return types.ReplyKeyboardForceReply()
