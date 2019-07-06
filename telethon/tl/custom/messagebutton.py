from .. import types, functions
from ...errors import BotTimeout
import webbrowser


class MessageButton:
    """
    .. note::

        `Message.buttons <telethon.tl.custom.message.Message.buttons>`
        are instances of this type. If you want to **define** a reply
        markup for e.g. sending messages, refer to `Button
        <telethon.tl.custom.button.Button>` instead.

    Custom class that encapsulates a message button providing
    an abstraction to easily access some commonly needed features
    (such as clicking the button itself).

    Attributes:

        button (:tl:`KeyboardButton`):
            The original :tl:`KeyboardButton` object.
    """
    def __init__(self, client, original, chat, bot, msg_id):
        self.button = original
        self._bot = bot
        self._chat = chat
        self._msg_id = msg_id
        self._client = client

    @property
    def client(self):
        """
        Returns the `telethon.client.telegramclient.TelegramClient`
        instance that created this instance.
        """
        return self._client

    @property
    def text(self):
        """The text string of the button."""
        return self.button.text

    @property
    def data(self):
        """The `bytes` data for :tl:`KeyboardButtonCallback` objects."""
        if isinstance(self.button, types.KeyboardButtonCallback):
            return self.button.data

    @property
    def inline_query(self):
        """The query `str` for :tl:`KeyboardButtonSwitchInline` objects."""
        if isinstance(self.button, types.KeyboardButtonSwitchInline):
            return self.button.query

    @property
    def url(self):
        """The url `str` for :tl:`KeyboardButtonUrl` objects."""
        if isinstance(self.button, types.KeyboardButtonUrl):
            return self.button.url

    async def click(self):
        """
        Emulates the behaviour of clicking this button.

        If it's a normal :tl:`KeyboardButton` with text, a message will be
        sent, and the sent `Message <telethon.tl.custom.message.Message>` returned.

        If it's an inline :tl:`KeyboardButtonCallback` with text and data,
        it will be "clicked" and the :tl:`BotCallbackAnswer` returned.

        If it's an inline :tl:`KeyboardButtonSwitchInline` button, the
        :tl:`StartBotRequest` will be invoked and the resulting updates
        returned.

        If it's a :tl:`KeyboardButtonUrl`, the URL of the button will
        be passed to ``webbrowser.open`` and return `True` on success.
        """
        if isinstance(self.button, types.KeyboardButton):
            return await self._client.send_message(
                self._chat, self.button.text, reply_to=self._msg_id)
        elif isinstance(self.button, types.KeyboardButtonCallback):
            req = functions.messages.GetBotCallbackAnswerRequest(
                peer=self._chat, msg_id=self._msg_id, data=self.button.data
            )
            try:
                return await self._client(req)
            except BotTimeout:
                return None
        elif isinstance(self.button, types.KeyboardButtonSwitchInline):
            return await self._client(functions.messages.StartBotRequest(
                bot=self._bot, peer=self._chat, start_param=self.button.query
            ))
        elif isinstance(self.button, types.KeyboardButtonUrl):
            return webbrowser.open(self.button.url)
        elif isinstance(self.button, types.KeyboardButtonGame):
            req = functions.messages.GetBotCallbackAnswerRequest(
                peer=self._chat, msg_id=self._msg_id, game=True
            )
            try:
                return await self._client(req)
            except BotTimeout:
                return None
