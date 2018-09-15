import abc
from .chatgetter import ChatGetter
from .sendergetter import SenderGetter
from .messagebutton import MessageButton
from .forward import Forward
from .. import TLObject, types, functions
from ... import utils, errors

# TODO Figure out a way to have the code generator error on missing fields
# Maybe parsing the init function alone if that's possible.
class Message(ChatGetter, SenderGetter, TLObject, abc.ABC):
    """
    This custom class aggregates both :tl:`Message` and
    :tl:`MessageService` to ease accessing their members.

    Remember that this class implements `ChatGetter
    <telethon.tl.custom.chatgetter.ChatGetter>` and `SenderGetter
    <telethon.tl.custom.sendergetter.SenderGetter>` which means you
    have access to all their sender and chat properties and methods.

    Members:
        id (`int`):
            The ID of this message. This field is *always* present.
            Any other member is optional and may be ``None``.

        out (`bool`):
            Whether the message is outgoing (i.e. you sent it from
            another session) or incoming (i.e. someone else sent it).

            Note that messages in your own chat are always incoming,
            but this member will be ``True`` if you send a message
            to your own chat. Messages you forward to your chat are
            *not* considered outgoing, just like official clients
            display them.

        mentioned (`bool`):
            Whether you were mentioned in this message or not.
            Note that replies to your own messages also count
            as mentions.

        media_unread (`bool`):
            Whether you have read the media in this message
            or not, e.g. listened to the voice note media.

        silent (`bool`):
            Whether this message should notify or not,
            used in channels.

        post (`bool`):
            Whether this message is a post in a broadcast
            channel or not.

        to_id (:tl:`Peer`):
            The peer to which this message was sent, which is either
            :tl:`PeerUser`, :tl:`PeerChat` or :tl:`PeerChannel`. This
            will always be present except for empty messages.

        date (`datetime`):
            The UTC+0 `datetime` object indicating when this message
            was sent. This will always be present except for empty
            messages.

        message (`str`):
            The string text of the message for :tl:`Message` instances,
            which will be ``None`` for other types of messages.

        action (:tl:`MessageAction`):
            The message action object of the message for :tl:`MessageService`
            instances, which will be ``None`` for other types of messages.

        from_id (`int`):
            The ID of the user who sent this message. This will be
            ``None`` if the message was sent in a broadcast channel.

        reply_to_msg_id (`int`):
            The ID to which this message is replying to, if any.

        fwd_from (:tl:`MessageFwdHeader`):
            The original forward header if this message is a forward.
            You should probably use the `forward` property instead.

        via_bot_id (`int`):
            The ID of the bot used to send this message
            through its inline mode (e.g. "via @like").

        media (:tl:`MessageMedia`):
            The media sent with this message if any (such as
            photos, videos, documents, gifs, stickers, etc.).

            You may want to access the `photo`, `document`
            etc. properties instead.

            If the media was not present or it was :tl:`MessageMediaEmpty`,
            this member will instead be ``None`` for convenience.

        reply_markup (:tl:`ReplyMarkup`):
            The reply markup for this message (which was sent
            either via a bot or by a bot). You probably want
            to access `buttons` instead.

        entities (List[:tl:`MessageEntity`]):
            The list of markup entities in this message,
            such as bold, italics, code, hyperlinks, etc.

        views (`int`):
            The number of views this message from a broadcast
            channel has. This is also present in forwards.

        edit_date (`datetime`):
            The date when this message was last edited.

        post_author (`str`):
            The display name of the message sender to
            show in messages sent to broadcast channels.

        grouped_id (`int`):
            If this message belongs to a group of messages
            (photo albums or video albums), all of them will
            have the same value here.
    """

    # region Initialization

    def __init__(
            # Common to all
            self, id,

            # Common to Message and MessageService (mandatory)
            to_id=None, date=None,

            # Common to Message and MessageService (flags)
            out=None, mentioned=None, media_unread=None, silent=None,
            post=None, from_id=None, reply_to_msg_id=None,

            # For Message (mandatory)
            message=None,

            # For Message (flags)
            fwd_from=None, via_bot_id=None, media=None, reply_markup=None,
            entities=None, views=None, edit_date=None, post_author=None,
            grouped_id=None,

            # For MessageAction (mandatory)
            action=None):
        # Common properties to all messages
        self.id = id
        self.to_id = to_id
        self.date = date
        self.out = out
        self.mentioned = mentioned
        self.media_unread = media_unread
        self.silent = silent
        self.post = post
        self.from_id = from_id
        self.reply_to_msg_id = reply_to_msg_id
        self.message = message
        self.fwd_from = fwd_from
        self.via_bot_id = via_bot_id
        self.media = None if isinstance(
            media, types.MessageMediaEmpty) else media

        self.reply_markup = reply_markup
        self.entities = entities
        self.views = views
        self.edit_date = edit_date
        self.post_author = post_author
        self.grouped_id = grouped_id
        self.action = action

        # Convenient storage for custom functions
        self._client = None
        self._text = None
        self._reply_message = None
        self._buttons = None
        self._buttons_flat = None
        self._buttons_count = None
        self._sender_id = from_id
        self._sender = None
        self._input_sender = None

        if not out and isinstance(to_id, types.PeerUser):
            self._chat_peer = types.PeerUser(from_id)
            if from_id == to_id.user_id:
                self.out = not self.fwd_from  # Patch out in our chat
        else:
            self._chat_peer = to_id

        if post and not from_id and self._chat_peer:
            # If the message comes from a Channel, let the sender be it
            self._sender_id = utils.get_peer_id(self._chat_peer)

        self._broadcast = post
        self._chat = None
        self._input_chat = None
        self._forward = None

    def _finish_init(self, client, entities, input_chat):
        """
        Finishes the initialization of this message by setting
        the client that sent the message and making use of the
        known entities.
        """
        self._client = client
        self._sender = entities.get(self._sender_id)
        if self._sender:
            self._input_sender = utils.get_input_peer(self._sender)
            if not getattr(self._input_sender, 'access_hash', True):
                self._input_sender = None

        self._chat = entities.get(self.chat_id)
        self._input_chat = input_chat
        if not self._input_chat and self._chat:
            self._input_chat = utils.get_input_peer(self._chat)
            if not getattr(self._input_chat, 'access_hash', True):
                # Telegram may omit the hash in updates -> invalid peer
                # However things like InputPeerSelf() or InputPeerChat(id)
                # are still valid so default to getting "True" on not found
                self._input_chat = None

        if self.fwd_from:
            self._forward = Forward(self._client, self.fwd_from, entities)

    # endregion Initialization

    # region Public Properties

    @property
    def client(self):
        """
        Returns the `telethon.client.telegramclient.TelegramClient`
        that patched this message. This will only be present if you
        **use the friendly methods**, it won't be there if you invoke
        raw API methods manually, in which case you should only access
        members, not properties.
        """
        return self._client

    @property
    def text(self):
        """
        The message text, formatted using the client's default
        parse mode. Will be ``None`` for :tl:`MessageService`.
        """
        if self._text is None and self._client:
            self._text = self._client.parse_mode.unparse(
                self.message, self.entities)

        return self._text

    @text.setter
    def text(self, value):
        self._text = value
        if self._client and self._client.parse_mode:
            self.message, self.entities = self._client.parse_mode.parse(value)
        else:
            self.message, self.entities = value, []

    @property
    def raw_text(self):
        """
        The raw message text, ignoring any formatting.
        Will be ``None`` for :tl:`MessageService`.

        Setting a value to this field will erase the
        `entities`, unlike changing the `message` member.
        """
        return self.message

    @raw_text.setter
    def raw_text(self, value):
        self.message = value
        self.entities = []
        self._text = None

    @property
    def is_reply(self):
        """
        True if the message is a reply to some other.

        Remember that you can access the ID of the message
        this one is replying to through `reply_to_msg_id`,
        and the `Message` object with `get_reply_message()`.
        """
        return bool(self.reply_to_msg_id)

    @property
    def forward(self):
        """
        Returns `Forward <telethon.tl.custom.forward.Forward>`
        if the message has been forwarded from somewhere else.
        """
        return self._forward

    @property
    def buttons(self):
        """
        Returns a matrix (list of lists) containing all buttons of the message
        as `MessageButton <telethon.tl.custom.messagebutton.MessageButton>`
        instances.
        """
        if self._buttons is None and self.reply_markup:
            if not self.input_chat:
                return
            try:
                bot = self._needed_markup_bot()
            except ValueError:
                return
            else:
                self._set_buttons(self._input_chat, bot)

        return self._buttons

    async def get_buttons(self):
        """
        Returns `buttons`, but will make an API call to find the
        input chat (needed for the buttons) unless it's already cached.
        """
        if not self.buttons and self.reply_markup:
            chat = await self.get_input_chat()
            if not chat:
                return
            try:
                bot = self._needed_markup_bot()
            except ValueError:
                await self._reload_message()
                bot = self._needed_markup_bot()  # TODO use via_input_bot

            self._set_buttons(chat, bot)

        return self._buttons

    @property
    def button_count(self):
        """
        Returns the total button count.
        """
        if self._buttons_count is None:
            if isinstance(self.reply_markup, (
                    types.ReplyInlineMarkup, types.ReplyKeyboardMarkup)):
                self._buttons_count = sum(
                    len(row.buttons) for row in self.reply_markup.rows)
            else:
                self._buttons_count = 0

        return self._buttons_count

    @property
    def photo(self):
        """
        If the message media is a photo, this returns the :tl:`Photo` object.
        This will also return the photo for :tl:`MessageService` if their
        action is :tl:`MessageActionChatEditPhoto`.
        """
        if isinstance(self.media, types.MessageMediaPhoto):
            if isinstance(self.media.photo, types.Photo):
                return self.media.photo
        elif isinstance(self.action, types.MessageActionChatEditPhoto):
            return self.action.photo
        else:
            web = self.web_preview
            if web and isinstance(web.photo, types.Photo):
                return web.photo

    @property
    def document(self):
        """
        If the message media is a document,
        this returns the :tl:`Document` object.
        """
        if isinstance(self.media, types.MessageMediaDocument):
            if isinstance(self.media.document, types.Document):
                return self.media.document
        else:
            web = self.web_preview
            if web and isinstance(web.photo, types.Document):
                return web.photo

    @property
    def web_preview(self):
        if isinstance(self.media, types.MessageMediaWebPage):
            if isinstance(self.media.webpage, types.WebPage):
                return self.media.webpage

    @property
    def audio(self):
        """
        If the message media is a document with an Audio attribute,
        this returns the :tl:`Document` object.
        """
        return self._document_by_attribute(types.DocumentAttributeAudio,
                                           lambda attr: not attr.voice)

    @property
    def voice(self):
        """
        If the message media is a document with a Voice attribute,
        this returns the :tl:`Document` object.
        """
        return self._document_by_attribute(types.DocumentAttributeAudio,
                                           lambda attr: attr.voice)

    @property
    def video(self):
        """
        If the message media is a document with a Video attribute,
        this returns the :tl:`Document` object.
        """
        return self._document_by_attribute(types.DocumentAttributeVideo)

    @property
    def video_note(self):
        """
        If the message media is a document with a Video attribute,
        this returns the :tl:`Document` object.
        """
        return self._document_by_attribute(types.DocumentAttributeVideo,
                                           lambda attr: attr.round_message)

    @property
    def gif(self):
        """
        If the message media is a document with an Animated attribute,
        this returns the :tl:`Document` object.
        """
        return self._document_by_attribute(types.DocumentAttributeAnimated)

    @property
    def sticker(self):
        """
        If the message media is a document with a Sticker attribute,
        this returns the :tl:`Document` object.
        """
        return self._document_by_attribute(types.DocumentAttributeSticker)

    # endregion Public Properties

    # region Public Methods

    def get_entities_text(self, cls=None):
        """
        Returns a list of tuples [(:tl:`MessageEntity`, `str`)], the string
        being the inner text of the message entity (like bold, italics, etc).

        Args:
            cls (`type`):
                Returns entities matching this type only. For example,
                the following will print the text for all ``code`` entities:

                >>> from telethon.tl.types import MessageEntityCode
                >>>
                >>> m = ...  # get the message
                >>> for _, inner_text in m.get_entities_text(MessageEntityCode):
                >>>     print(inner_text)
        """
        ent = self.entities
        if not ent:
            return []

        if cls:
            ent = [c for c in ent if isinstance(c, cls)]

        texts = utils.get_inner_text(self.message, ent)
        return list(zip(ent, texts))

    async def get_reply_message(self):
        """
        The `Message` that this message is replying to, or ``None``.

        The result will be cached after its first use.
        """
        if self._reply_message is None:
            if not self.reply_to_msg_id:
                return None

            self._reply_message = await self._client.get_messages(
                await self.get_input_chat() if self.is_channel else None,
                ids=self.reply_to_msg_id
            )

        return self._reply_message

    async def respond(self, *args, **kwargs):
        """
        Responds to the message (not as a reply). Shorthand for
        `telethon.client.messages.MessageMethods.send_message`
        with ``entity`` already set.
        """
        return await self._client.send_message(
            await self.get_input_chat(), *args, **kwargs)

    async def reply(self, *args, **kwargs):
        """
        Replies to the message (as a reply). Shorthand for
        `telethon.client.messages.MessageMethods.send_message`
        with both ``entity`` and ``reply_to`` already set.
        """
        kwargs['reply_to'] = self.id
        return await self._client.send_message(
            await self.get_input_chat(), *args, **kwargs)

    async def forward_to(self, *args, **kwargs):
        """
        Forwards the message. Shorthand for
        `telethon.client.messages.MessageMethods.forward_messages`
        with both ``messages`` and ``from_peer`` already set.

        If you need to forward more than one message at once, don't use
        this `forward_to` method. Use a
        `telethon.client.telegramclient.TelegramClient` instance directly.
        """
        kwargs['messages'] = self.id
        kwargs['from_peer'] = await self.get_input_chat()
        return await self._client.forward_messages(*args, **kwargs)

    async def edit(self, *args, **kwargs):
        """
        Edits the message iff it's outgoing. Shorthand for
        `telethon.client.messages.MessageMethods.edit_message`
        with both ``entity`` and ``message`` already set.

        Returns ``None`` if the message was incoming,
        or the edited `Message` otherwise.
        """
        if self.fwd_from or not self.out:
            return None  # We assume self.out was patched for our chat

        return await self._client.edit_message(
            await self.get_input_chat(), self.id,
            *args, **kwargs
        )

    async def delete(self, *args, **kwargs):
        """
        Deletes the message. You're responsible for checking whether you
        have the permission to do so, or to except the error otherwise.
        Shorthand for
        `telethon.client.messages.MessageMethods.delete_messages` with
        ``entity`` and ``message_ids`` already set.

        If you need to delete more than one message at once, don't use
        this `delete` method. Use a
        `telethon.client.telegramclient.TelegramClient` instance directly.
        """
        return await self._client.delete_messages(
            await self.get_input_chat(), [self.id],
            *args, **kwargs
        )

    async def download_media(self, *args, **kwargs):
        """
        Downloads the media contained in the message, if any. Shorthand
        for `telethon.client.downloads.DownloadMethods.download_media`
        with the ``message`` already set.
        """
        return await self._client.download_media(self, *args, **kwargs)

    async def click(self, i=None, j=None,
                    *, text=None, filter=None, data=None):
        """
        Calls `telethon.tl.custom.messagebutton.MessageButton.click`
        for the specified button.

        Does nothing if the message has no buttons.

        Args:
            i (`int`):
                Clicks the i'th button (starting from the index 0).
                Will ``raise IndexError`` if out of bounds. Example:

                >>> message = ...  # get the message somehow
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

            data (`bytes`):
                This argument overrides the rest and will not search any
                buttons. Instead, it will directly send the request to
                behave as if it clicked a button with said data. Note
                that if the message does not have this data, it will
                ``raise DataInvalidError``.
        """
        if data:
            if not await self.get_input_chat():
                return None

            try:
                return await self._client(
                    functions.messages.GetBotCallbackAnswerRequest(
                        peer=self._input_chat,
                        msg_id=self.id,
                        data=data
                    )
                )
            except errors.BotTimeout:
                return None

        if sum(int(x is not None) for x in (i, text, filter)) >= 2:
            raise ValueError('You can only set either of i, text or filter')

        if not await self.get_buttons():
            return  # Accessing the property sets self._buttons[_flat]

        if text is not None:
            if callable(text):
                for button in self._buttons_flat:
                    if text(button.text):
                        return await button.click()
            else:
                for button in self._buttons_flat:
                    if button.text == text:
                        return await button.click()
            return

        if filter is not None:
            for button in self._buttons_flat:
                if filter(button):
                    return await button.click()
            return

        if i is None:
            i = 0
        if j is None:
            return await self._buttons_flat[i].click()
        else:
            return await self._buttons[i][j].click()

    # endregion Public Methods

    # region Private Methods

    # TODO Make a property for via_bot and via_input_bot, as well as get_*
    async def _reload_message(self):
        """
        Re-fetches this message to reload the sender and chat entities,
        along with their input versions.
        """
        try:
            chat = await self.get_input_chat() if self.is_channel else None
            msg = await self._client.get_messages(chat, ids=self.id)
        except ValueError:
            return  # We may not have the input chat/get message failed
        if not msg:
            return  # The message may be deleted and it will be None

        self._sender = msg._sender
        self._input_sender = msg._input_sender
        self._chat = msg._chat
        self._input_chat = msg._input_chat

    async def _refetch_sender(self):
        await self._reload_message()

    def _set_buttons(self, chat, bot):
        """
        Helper methods to set the buttons given the input sender and chat.
        """
        if isinstance(self.reply_markup, (
                types.ReplyInlineMarkup, types.ReplyKeyboardMarkup)):
            self._buttons = [[
                MessageButton(self._client, button, chat, bot, self.id)
                for button in row.buttons
            ] for row in self.reply_markup.rows]
            self._buttons_flat = [x for row in self._buttons for x in row]

    def _needed_markup_bot(self):
        """
        Returns the input peer of the bot that's needed for the reply markup.

        This is necessary for :tl:`KeyboardButtonSwitchInline` since we need
        to know what bot we want to start. Raises ``ValueError`` if the bot
        cannot be found but is needed. Returns ``None`` if it's not needed.
        """
        if not isinstance(self.reply_markup, (
                types.ReplyInlineMarkup, types.ReplyKeyboardMarkup)):
            return None

        for row in self.reply_markup.rows:
            for button in row.buttons:
                if isinstance(button, types.KeyboardButtonSwitchInline):
                    if button.same_peer:
                        bot = self.input_sender
                        if not bot:
                            raise ValueError('No input sender')
                    else:
                        return self._client.session.get_input_entity(
                            self.via_bot_id)

    def _document_by_attribute(self, kind, condition=None):
        """
        Helper method to return the document only if it has an attribute
        that's an instance of the given kind, and passes the condition.
        """
        doc = self.document
        if doc:
            for attr in doc.attributes:
                if isinstance(attr, kind):
                    if not condition or condition(doc):
                        return doc
                    return None

    # endregion Private Methods
