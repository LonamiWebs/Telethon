from .. import types


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
    You can also configure the aspect of the reply with these.

    You **cannot** mix the two type of buttons together,
    and it will error if you try to do so.

    The text for all buttons may be at most 142 characters.
    If more characters are given, Telegram will cut the text
    to 128 characters and add the ellipsis (…) character as
    the 129.
    """
    def __init__(self, button, *, resize, single_use, selective):
        self.button = button
        self.resize = resize
        self.single_use = single_use
        self.selective = selective

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
        Creates a new inline button with some payload data in it.

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
        Creates a new inline button to switch to inline query.

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
        Creates a new inline button to open the desired URL on click.

        If no `url` is given, the `text` will be used as said URL instead.

        You cannot detect that the user clicked this button directly.
        """
        return types.KeyboardButtonUrl(text, url or text)

    @classmethod
    def text(cls, text, *, resize=None, single_use=None, selective=None):
        """
        Creates a new keyboard button with the given text.

        Args:
            resize (`bool`):
                If present, the entire keyboard will be reconfigured to
                be resized and be smaller if there are not many buttons.

            single_use (`bool`):
                If present, the entire keyboard will be reconfigured to
                be usable only once before it hides itself.

            selective (`bool`):
                If present, the entire keyboard will be reconfigured to
                be "selective". The keyboard will be shown only to specific
                users. It will target users that are @mentioned in the text
                of the message or to the sender of the message you reply to.
        """
        return cls(types.KeyboardButton(text),
                   resize=resize, single_use=single_use, selective=selective)

    @classmethod
    def request_location(cls, text, *,
                         resize=None, single_use=None, selective=None):
        """
        Creates a new keyboard button to request the user's location on click.

        ``resize``, ``single_use`` and ``selective`` are documented in `text`.
        """
        return cls(types.KeyboardButtonRequestGeoLocation(text),
                   resize=resize, single_use=single_use, selective=selective)

    @classmethod
    def request_phone(cls, text, *,
                      resize=None, single_use=None, selective=None):
        """
        Creates a new keyboard button to request the user's phone on click.

        ``resize``, ``single_use`` and ``selective`` are documented in `text`.
        """
        return cls(types.KeyboardButtonRequestPhone(text),
                   resize=resize, single_use=single_use, selective=selective)

    @staticmethod
    def clear():
        """
        Clears all keyboard buttons after sending a message with this markup.
        When used, no other button should be present or it will be ignored.
        """
        return types.ReplyKeyboardHide()

    @staticmethod
    def force_reply():
        """
        Forces a reply to the message with this markup. If used,
        no other button should be present or it will be ignored.
        """
        return types.ReplyKeyboardForceReply()
