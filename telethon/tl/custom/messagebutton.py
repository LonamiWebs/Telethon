from .. import types, functions
from ... import password as pwd_mod
from ...errors import BotResponseTimeoutError
try:
    import webbrowser
except ModuleNotFoundError:
    pass
import sys
import os


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

    async def click(self, share_phone=None, share_geo=None, *, password=None, open_url=None):
        """
        Emulates the behaviour of clicking this button.

        If it's a normal :tl:`KeyboardButton` with text, a message will be
        sent, and the sent `Message <telethon.tl.custom.message.Message>` returned.

        If it's an inline :tl:`KeyboardButtonCallback` with text and data,
        it will be "clicked" and the :tl:`BotCallbackAnswer` returned.

        If it's an inline :tl:`KeyboardButtonSwitchInline` button, the
        :tl:`StartBotRequest` will be invoked and the resulting updates
        returned.

        If it's a :tl:`KeyboardButtonUrl`, the ``URL`` of the button will
        be returned. If you pass ``open_url=True`` the URL of the button will
        be passed to ``webbrowser.open`` and return `True` on success.

        If it's a :tl:`KeyboardButtonRequestPhone`, you must indicate that you
        want to ``share_phone=True`` in order to share it. Sharing it is not a
        default because it is a privacy concern and could happen accidentally.

        You may also use ``share_phone=phone`` to share a specific number, in
        which case either `str` or :tl:`InputMediaContact` should be used.

        If it's a :tl:`KeyboardButtonRequestGeoLocation`, you must pass a
        tuple in ``share_geo=(longitude, latitude)``. Note that Telegram seems
        to have some heuristics to determine impossible locations, so changing
        this value a lot quickly may not work as expected. You may also pass a
        :tl:`InputGeoPoint` if you find the order confusing.
        """
        if isinstance(self.button, types.KeyboardButton):
            return await self._client.send_message(
                self._chat, self.button.text, parse_mode=None)
        elif isinstance(self.button, types.KeyboardButtonCallback):
            if password is not None:
                pwd = await self._client(functions.account.GetPasswordRequest())
                password = pwd_mod.compute_check(pwd, password)

            req = functions.messages.GetBotCallbackAnswerRequest(
                peer=self._chat, msg_id=self._msg_id, data=self.button.data,
                password=password
            )
            try:
                return await self._client(req)
            except BotResponseTimeoutError:
                return None
        elif isinstance(self.button, types.KeyboardButtonSwitchInline):
            return await self._client(functions.messages.StartBotRequest(
                bot=self._bot, peer=self._chat, start_param=self.button.query
            ))
        elif isinstance(self.button, types.KeyboardButtonUrl):
            if open_url:
                if "webbrowser" in sys.modules:
                    return webbrowser.open(self.button.url)
            return self.button.url
        elif isinstance(self.button, types.KeyboardButtonGame):
            req = functions.messages.GetBotCallbackAnswerRequest(
                peer=self._chat, msg_id=self._msg_id, game=True
            )
            try:
                return await self._client(req)
            except BotResponseTimeoutError:
                return None
        elif isinstance(self.button, types.KeyboardButtonRequestPhone):
            if not share_phone:
                raise ValueError('cannot click on phone buttons unless share_phone=True')

            if share_phone == True or isinstance(share_phone, str):
                me = await self._client.get_me()
                share_phone = types.InputMediaContact(
                    phone_number=me.phone if share_phone == True else share_phone,
                    first_name=me.first_name or '',
                    last_name=me.last_name or '',
                    vcard=''
                )

            return await self._client.send_file(self._chat, share_phone)
        elif isinstance(self.button, types.KeyboardButtonRequestGeoLocation):
            if not share_geo:
                raise ValueError('cannot click on geo buttons unless share_geo=(longitude, latitude)')

            if isinstance(share_geo, (tuple, list)):
                long, lat = share_geo
                share_geo = types.InputMediaGeoPoint(types.InputGeoPoint(lat=lat, long=long))

            return await self._client.send_file(self._chat, share_geo)
