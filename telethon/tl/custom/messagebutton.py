from .. import types, functions
import webbrowser


class MessageButton:
    """
    Custom class that encapsulates a message providing an abstraction to
    easily access some commonly needed features (such as the markdown text
    or the text for a given message entity).

    Attributes:

        button (:tl:`KeyboardButton`):
            The original :tl:`KeyboardButton` object.
    """
    def __init__(self, client, original, from_user, chat, msg_id):
        self.button = original
        self._from = from_user
        self._chat = chat
        self._msg_id = msg_id
        self._client = client

    @property
    def client(self):
        """
        Returns the `telethon.telegram_client.TelegramClient` instance that
        created this instance.
        """
        return self._client

    @property
    def text(self):
        """The text string of the button."""
        return self.button.text

    @property
    def data(self):
        """The ``bytes`` data for :tl:`KeyboardButtonCallback` objects."""
        if isinstance(self.button, types.KeyboardButtonCallback):
            return self.button.data

    @property
    def inline_query(self):
        """The query ``str`` for :tl:`KeyboardButtonSwitchInline` objects."""
        if isinstance(self.button, types.KeyboardButtonSwitchInline):
            return self.button.query

    @property
    def url(self):
        """The url ``str`` for :tl:`KeyboardButtonUrl` objects."""
        if isinstance(self.button, types.KeyboardButtonUrl):
            return self.button.url

    def click(self):
        """
        Clicks the inline keyboard button of the message, if any.

        If the message has a non-inline keyboard, clicking it will
        send the message, switch to inline, or open its URL.
        """
        if isinstance(self.button, types.KeyboardButton):
            return self._client.send_message(
                self._chat, self.button.text, reply_to=self._msg_id)
        elif isinstance(self.button, types.KeyboardButtonCallback):
            return self._client(functions.messages.GetBotCallbackAnswerRequest(
                peer=self._chat, msg_id=self._msg_id, data=self.button.data
            ), retries=1)
        elif isinstance(self.button, types.KeyboardButtonSwitchInline):
            return self._client(functions.messages.StartBotRequest(
                bot=self._from, peer=self._chat, start_param=self.button.query
            ), retries=1)
        elif isinstance(self.button, types.KeyboardButtonUrl):
            return webbrowser.open(self.button.url)
