from .. import types
from ...extensions import markdown
from ...utils import get_input_peer, get_peer_id
from .messagebutton import MessageButton


class Message:
    """
    Custom class that encapsulates a message providing an abstraction to
    easily access some commonly needed features (such as the markdown text
    or the text for a given message entity).

    Attributes:

        original_message (:tl:`Message`):
            The original :tl:`Message` object.

        Any other attribute:
            Attributes not described here are the same as those available
            in the original :tl:`Message`.
    """
    def __init__(self, client, original, entities, input_chat):
        self.original_message = original
        self.stringify = self.original_message.stringify
        self.to_dict = self.original_message.to_dict
        self._client = client
        self._text = None
        self._reply_to = None
        self._buttons = None
        self._buttons_flat = []
        self._sender = entities.get(self.original_message.from_id)
        self._chat = entities.get(get_peer_id(self.original_message.to_id))
        self._input_sender = None
        self._input_chat = input_chat
        self._fwd_from_entity = None
        if getattr(self.original_message, 'fwd_from', None):
            fwd = self.original_message.fwd_from
            if fwd.from_id:
                self._fwd_from_entity = entities.get(fwd.from_id)
            elif fwd.channel_id:
                self._fwd_from_entity = entities.get(get_peer_id(
                    types.PeerChannel(fwd.channel_id)))

    def __getattr__(self, item):
        return getattr(self.original_message, item)

    def __str__(self):
        return str(self.original_message)

    def __repr__(self):
        return repr(self.original_message)

    @property
    def client(self):
        return self._client

    @property
    def text(self):
        """
        The message text, markdown-formatted.
        Will be ``None`` for :tl:`MessageService`.
        """
        if self._text is None\
                and isinstance(self.original_message, types.Message):
            if not self.original_message.entities:
                return self.original_message.message
            self._text = markdown.unparse(self.original_message.message,
                                          self.original_message.entities or [])
        return self._text

    @property
    def raw_text(self):
        """
        The raw message text, ignoring any formatting.
        Will be ``None`` for :tl:`MessageService`.
        """
        if isinstance(self.original_message, types.Message):
            return self.original_message.message

    @property
    def message(self):
        """
        The raw message text, ignoring any formatting.
        Will be ``None`` for :tl:`MessageService`.
        """
        return self.raw_text

    @property
    def action(self):
        """
        The :tl:`MessageAction` for the :tl:`MessageService`.
        Will be ``None`` for :tl:`Message`.
        """
        if isinstance(self.original_message, types.MessageService):
            return self.original_message.action

    @property
    def sender(self):
        if self._sender is None:
            self._sender = self._client.get_entity(self.input_sender)
        return self._sender

    @property
    def chat(self):
        if self._chat is None:
            self._chat = self._client.get_entity(self.input_chat)
        return self._chat

    @property
    def input_sender(self):
        if self._input_sender is None:
            if self._sender is not None:
                self._input_sender = get_input_peer(self._sender)
            else:
                self._input_sender = self._client.get_input_entity(
                    self.original_message.from_id)
        return self._input_sender

    @property
    def input_chat(self):
        if self._input_chat is None:
            if self._chat is not None:
                self._chat = get_input_peer(self._chat)
            else:
                self._chat = self._client.get_input_entity(
                    self.original_message.to_id)
        return self._input_chat

    @property
    def user_id(self):
        return self.original_message.from_id

    @property
    def chat_id(self):
        return get_peer_id(self.original_message.to_id)

    @property
    def buttons(self):
        """
        Returns a matrix (list of lists) containing all buttons of the message
        as `telethon.tl.custom.messagebutton.MessageButton` instances.
        """
        if self._buttons is None and self.original_message.reply_markup:
            if isinstance(self.original_message.reply_markup, (
                    types.ReplyInlineMarkup, types.ReplyKeyboardMarkup)):
                self._buttons = [[
                    MessageButton(self._client, button, self.input_sender,
                                  self.input_chat, self.original_message.id)
                    for button in row.buttons
                ] for row in self.original_message.reply_markup.rows]
                self._buttons_flat = [x for row in self._buttons for x in row]
        return self._buttons

    @property
    def button_count(self):
        """
        Returns the total button count.
        """
        return len(self._buttons_flat) if self.buttons else 0

    @property
    def reply_to(self):
        """
        The :tl:`Message` that this message is replying to, or ``None``.

        Note that this will make a network call to fetch the message and
        will later be cached.
        """
        if self._reply_to is None:
            if not self.original_message.reply_to_msg_id:
                return None
            self._reply_to = self._client.get_messages(
                self.original_message.to_id,
                ids=self.original_message.reply_to_msg_id
            )

    @property
    def fwd_from_entity(self):
        """
        If the :tl:`Message` is a forwarded message, returns the :tl:`User`
        or :tl:`Channel` who originally sent the message, or ``None``.
        """
        if self._fwd_from_entity is None:
            if getattr(self.original_message, 'fwd_from', None):
                fwd = self.original_message.fwd_from
                if fwd.from_id:
                    self._fwd_from_entity = self._client.get_entity(
                        fwd.from_id)
                elif fwd.channel_id:
                    self._fwd_from_entity = self._client.get_entity(
                        get_peer_id(types.PeerChannel(fwd.channel_id)))
        return self._fwd_from_entity

    def reply(self, *args, **kwargs):
        """
        Replies to the message (as a reply). Shorthand for
        `telethon.telegram_client.TelegramClient.send_message` with
        both ``entity`` and ``reply_to`` already set.
        """
        kwargs['reply_to'] = self.original_message.id
        return self._client.send_message(self.original_message.to_id,
                                         *args, **kwargs)

    def download_media(self, *args, **kwargs):
        """
        Downloads the media contained in the message, if any.
        `telethon.telegram_client.TelegramClient.download_media` with
        the ``message`` already set.
        """
        return self._client.download_media(self.original_message,
                                           *args, **kwargs)

    def get_entities_text(self):
        """
        Returns a list of tuples [(:tl:`MessageEntity`, `str`)], the string
        being the inner text of the message entity (like bold, italics, etc).
        """
        texts = markdown.get_inner_text(self.original_message.message,
                                        self.original_message.entities)
        return list(zip(self.original_message.entities, texts))

    def click(self, i=None, j=None, *, text=None, filter=None):
        """
        Clicks the inline keyboard button of the message, if any.

        If the message has a non-inline keyboard, clicking it will
        send the message, switch to inline, or open its URL.

        Args:
            i (`int`):
                Clicks the i'th button (starting from the index 0).
                Will ``raise IndexError`` if out of bounds. Example:

                >>> message = Message(...)
                >>> # Clicking the 3rd button
                >>> # [button1] [button2]
                >>> # [     button3     ]
                >>> # [button4] [button5]
                >>> message.click(2)  # index

            j (`int`):
                Clicks the button at position (i, j), these being the
                indices for the (row, column) respectively. Example:

                >>> # Clicking the 2nd button on the 1st row.
                >>> # [button1] [button2]
                >>> # [     button3     ]
                >>> # [button4] [button5]
                >>> message.click(0, 1)  # (row, column)

                This is equivalent to ``message.buttons[0][1].click()``.

            text (`str` | `callable`):
                Clicks the first button with the text "text". This may
                also be a callable, like a ``re.compile(...).match``,
                and the text will be passed to it.

            filter (`callable`):
                Clicks the first button for which the callable
                returns ``True``. The callable should accept a single
                `telethon.tl.custom.messagebutton.MessageButton` argument.
        """
        if sum(int(x is not None) for x in (i, text, filter)) >= 2:
            raise ValueError('You can only set either of i, text or filter')

        if text is not None:
            if callable(text):
                for button in self._buttons_flat:
                    if text(button.text):
                        return button.click()
            else:
                for button in self._buttons_flat:
                    if button.text == text:
                        return button.click()
            return

        if filter is not None:
            for button in self._buttons_flat:
                if filter(button):
                    return button.click()
            return

        if i is None:
            i = 0
        if j is None:
            return self._buttons_flat[i].click()
        else:
            return self._buttons[i][j].click()
