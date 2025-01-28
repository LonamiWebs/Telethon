from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
from .chatgetter import ChatGetter
from .sendergetter import SenderGetter
from .messagebutton import MessageButton
from .forward import Forward
from .file import File
from .. import TLObject, types, functions, alltlobjects
from ... import utils, errors


# TODO Figure out a way to have the code generator error on missing fields
# Maybe parsing the init function alone if that's possible.
class Message(ChatGetter, SenderGetter, TLObject):
    """
    This custom class aggregates both :tl:`Message` and
    :tl:`MessageService` to ease accessing their members.

    Remember that this class implements `ChatGetter
    <telethon.tl.custom.chatgetter.ChatGetter>` and `SenderGetter
    <telethon.tl.custom.sendergetter.SenderGetter>` which means you
    have access to all their sender and chat properties and methods.

    Members:
        out (`bool`):
            Whether the message is outgoing (i.e. you sent it from
            another session) or incoming (i.e. someone else sent it).

            Note that messages in your own chat are always incoming,
            but this member will be `True` if you send a message
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
            Whether the message should notify people with sound or not.
            Previously used in channels, but since 9 August 2019, it can
            also be `used in private chats
            <https://telegram.org/blog/silent-messages-slow-mode>`_.

        post (`bool`):
            Whether this message is a post in a broadcast
            channel or not.

        from_scheduled (`bool`):
            Whether this message was originated from a previously-scheduled
            message or not.

        legacy (`bool`):
            Whether this is a legacy message or not.

        edit_hide (`bool`):
            Whether the edited mark of this message is edited
            should be hidden (e.g. in GUI clients) or shown.

        pinned (`bool`):
            Whether this message is currently pinned or not.

        noforwards (`bool`):
            Whether this message can be forwarded or not.

        invert_media (`bool`):
            Whether the media in this message should be inverted.
            
        offline (`bool`):
            Whether the message was sent by an implicit action, for example, as an away or a greeting business message, or as a scheduled message.

        id (`int`):
            The ID of this message. This field is *always* present.
            Any other member is optional and may be `None`.

        from_id (:tl:`Peer`):
            The peer who sent this message, which is either
            :tl:`PeerUser`, :tl:`PeerChat` or :tl:`PeerChannel`.
            This value will be `None` for anonymous messages.

        peer_id (:tl:`Peer`):
            The peer to which this message was sent, which is either
            :tl:`PeerUser`, :tl:`PeerChat` or :tl:`PeerChannel`. This
            will always be present except for empty messages.

        fwd_from (:tl:`MessageFwdHeader`):
            The original forward header if this message is a forward.
            You should probably use the `forward` property instead.

        via_bot_id (`int`):
            The ID of the bot used to send this message
            through its inline mode (e.g. "via @like").

        reply_to (:tl:`MessageReplyHeader`):
            The original reply header if this message is replying to another.

        date (`datetime`):
            The UTC+0 `datetime` object indicating when this message
            was sent. This will always be present except for empty
            messages.

        message (`str`):
            The string text of the message for `Message
            <telethon.tl.custom.message.Message>` instances,
            which will be `None` for other types of messages.

        media (:tl:`MessageMedia`):
            The media sent with this message if any (such as
            photos, videos, documents, gifs, stickers, etc.).

            You may want to access the `photo`, `document`
            etc. properties instead.

            If the media was not present or it was :tl:`MessageMediaEmpty`,
            this member will instead be `None` for convenience.

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

        forwards (`int`):
            The number of times this message has been forwarded.

        replies (`int`):
            The number of times another message has replied to this message.

        edit_date (`datetime`):
            The date when this message was last edited.

        post_author (`str`):
            The display name of the message sender to
            show in messages sent to broadcast channels.

        grouped_id (`int`):
            If this message belongs to a group of messages
            (photo albums or video albums), all of them will
            have the same value here.

        reactions (:tl:`MessageReactions`)
            Reactions to this message.

        restriction_reason (List[:tl:`RestrictionReason`])
            An optional list of reasons why this message was restricted.
            If the list is `None`, this message has not been restricted.

        ttl_period (`int`):
            The Time To Live period configured for this message.
            The message should be erased from wherever it's stored (memory, a
            local database, etc.) when
            ``datetime.now() > message.date + timedelta(seconds=message.ttl_period)``.

        action (:tl:`MessageAction`):
            The message action object of the message for :tl:`MessageService`
            instances, which will be `None` for other types of messages.

        saved_peer_id (:tl:`Peer`)
    """

    # region Initialization

    def __init__(
            self,
            id: int, peer_id: types.TypePeer,
            date: Optional[datetime]=None, message: Optional[str]=None,
            # Copied from Message.__init__ signature
            out: Optional[bool]=None, mentioned: Optional[bool]=None, media_unread: Optional[bool]=None, silent: Optional[bool]=None, post: Optional[bool]=None, from_scheduled: Optional[bool]=None, legacy: Optional[bool]=None, edit_hide: Optional[bool]=None, pinned: Optional[bool]=None, noforwards: Optional[bool]=None, invert_media: Optional[bool]=None, offline: Optional[bool]=None, video_processing_pending: Optional[bool]=None, from_id: Optional[types.TypePeer]=None, from_boosts_applied: Optional[int]=None, saved_peer_id: Optional[types.TypePeer]=None, fwd_from: Optional[types.TypeMessageFwdHeader]=None, via_bot_id: Optional[int]=None, via_business_bot_id: Optional[int]=None, reply_to: Optional[types.TypeMessageReplyHeader]=None, media: Optional[types.TypeMessageMedia]=None, reply_markup: Optional[types.TypeReplyMarkup]=None, entities: Optional[List[types.TypeMessageEntity]]=None, views: Optional[int]=None, forwards: Optional[int]=None, replies: Optional[types.TypeMessageReplies]=None, edit_date: Optional[datetime]=None, post_author: Optional[str]=None, grouped_id: Optional[int]=None, reactions: Optional[types.TypeMessageReactions]=None, restriction_reason: Optional[List[types.TypeRestrictionReason]]=None, ttl_period: Optional[int]=None, quick_reply_shortcut_id: Optional[int]=None, effect: Optional[int]=None, factcheck: Optional[types.TypeFactCheck]=None, report_delivery_until_date: Optional[datetime]=None,
            # Copied from MessageService.__init__ signature
            action: Optional[types.TypeMessageAction]=None, reactions_are_possible: Optional[bool]=None
    ):
        # Copied from Message.__init__ body
        self.id = id
        self.peer_id = peer_id
        self.date = date
        self.message = message
        self.out = bool(out)
        self.mentioned = mentioned
        self.media_unread = media_unread
        self.silent = silent
        self.post = post
        self.from_scheduled = from_scheduled
        self.legacy = legacy
        self.edit_hide = edit_hide
        self.pinned = pinned
        self.noforwards = noforwards
        self.invert_media = invert_media
        self.offline = offline
        self.video_processing_pending = video_processing_pending
        self.from_id = from_id
        self.from_boosts_applied = from_boosts_applied
        self.saved_peer_id = saved_peer_id
        self.fwd_from = fwd_from
        self.via_bot_id = via_bot_id
        self.via_business_bot_id = via_business_bot_id
        self.reply_to = reply_to
        self.media = None if isinstance(media, types.MessageMediaEmpty) else media
        self.reply_markup = reply_markup
        self.entities = entities
        self.views = views
        self.forwards = forwards
        self.replies = replies
        self.edit_date = edit_date
        self.post_author = post_author
        self.grouped_id = grouped_id
        self.reactions = reactions
        self.restriction_reason = restriction_reason
        self.ttl_period = ttl_period
        self.quick_reply_shortcut_id = quick_reply_shortcut_id
        self.effect = effect
        self.factcheck = factcheck
        self.report_delivery_until_date = report_delivery_until_date
        # Copied from MessageService.__init__ body
        self.action = action
        self.reactions_are_possible = reactions_are_possible

        # Convenient storage for custom functions
        # TODO This is becoming a bit of bloat
        self._client = None
        self._text = None
        self._file = None
        self._reply_message = None
        self._buttons = None
        self._buttons_flat = None
        self._buttons_count = None
        self._via_bot = None
        self._via_input_bot = None
        self._action_entities = None
        self._linked_chat = None

        sender_id = None
        if from_id is not None:
            sender_id = utils.get_peer_id(from_id)
        elif peer_id:
            # If the message comes from a Channel, let the sender be it
            # ...or...
            # incoming messages in private conversations no longer have from_id
            # (layer 119+), but the sender can only be the chat we're in.
            if post or (not out and isinstance(peer_id, types.PeerUser)):
                sender_id = utils.get_peer_id(peer_id)

        # Note that these calls would reset the client
        ChatGetter.__init__(self, peer_id, broadcast=post)
        SenderGetter.__init__(self, sender_id)

        self._forward = None
        self._reply_to_chat = None
        self._reply_to_sender = None

    def _finish_init(self, client, entities, input_chat):
        """
        Finishes the initialization of this message by setting
        the client that sent the message and making use of the
        known entities.
        """
        self._client = client

        # Make messages sent to ourselves outgoing unless they're forwarded.
        # This makes it consistent with official client's appearance.
        if self.peer_id == types.PeerUser(client._self_id) and not self.fwd_from:
            self.out = True

        cache = client._mb_entity_cache

        self._sender, self._input_sender = utils._get_entity_pair(
            self.sender_id, entities, cache)

        self._chat, self._input_chat = utils._get_entity_pair(
            self.chat_id, entities, cache)

        if input_chat:  # This has priority
            self._input_chat = input_chat

        if self.via_bot_id:
            self._via_bot, self._via_input_bot = utils._get_entity_pair(
                self.via_bot_id, entities, cache)

        if self.fwd_from:
            self._forward = Forward(self._client, self.fwd_from, entities)

        if self.action:
            if isinstance(self.action, (types.MessageActionChatAddUser,
                                        types.MessageActionChatCreate)):
                self._action_entities = [entities.get(i)
                                         for i in self.action.users]
            elif isinstance(self.action, types.MessageActionChatDeleteUser):
                self._action_entities = [entities.get(self.action.user_id)]
            elif isinstance(self.action, types.MessageActionChatJoinedByLink):
                self._action_entities = [entities.get(self.action.inviter_id)]
            elif isinstance(self.action, types.MessageActionChatMigrateTo):
                self._action_entities = [entities.get(utils.get_peer_id(
                    types.PeerChannel(self.action.channel_id)))]
            elif isinstance(
                    self.action, types.MessageActionChannelMigrateFrom):
                self._action_entities = [entities.get(utils.get_peer_id(
                    types.PeerChat(self.action.chat_id)))]

        if self.replies and self.replies.channel_id:
            self._linked_chat = entities.get(utils.get_peer_id(
                    types.PeerChannel(self.replies.channel_id)))
        
        if isinstance(self.reply_to, types.MessageReplyHeader):
            if self.reply_to.reply_to_peer_id:
                self._reply_to_chat = entities.get(utils.get_peer_id(self.reply_to.reply_to_peer_id))
            if self.reply_to.reply_from:
                if self.reply_to.reply_from.from_id:
                    self._reply_to_sender = entities.get(utils.get_peer_id(self.reply_to.reply_from.from_id))



    # endregion Initialization

    # region Public Properties

    @property
    def client(self):
        """
        Returns the `TelegramClient <telethon.client.telegramclient.TelegramClient>`
        that *patched* this message. This will only be present if you
        **use the friendly methods**, it won't be there if you invoke
        raw API methods manually, in which case you should only access
        members, not properties.
        """
        return self._client

    @property
    def text(self):
        """
        The message text, formatted using the client's default
        parse mode. Will be `None` for :tl:`MessageService`.
        """
        if self._text is None and self._client:
            if not self._client.parse_mode:
                self._text = self.message
            else:
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
        Will be `None` for :tl:`MessageService`.

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
        `True` if the message is a reply to some other message.

        Remember that you can access the ID of the message
        this one is replying to through `reply_to.reply_to_msg_id`,
        and the `Message` object with `get_reply_message()`.
        """
        return self.reply_to is not None

    @property
    def forward(self):
        """
        The `Forward <telethon.tl.custom.forward.Forward>`
        information if this message is a forwarded message.
        """
        return self._forward

    @property
    def reply_to_chat(self):
        """
        The :tl:`Channel` in which the replied-to message was sent,
        if this message is a reply in another chat
        """
        return self._reply_to_chat

    @property
    def reply_to_sender(self):
        """
        The :tl:`User`, :tl:`Channel`, or whatever other entity that
        sent the replied-to message, if this message is a reply in another chat.
        """
        return self._reply_to_sender

    @property
    def buttons(self):
        """
        Returns a list of lists of `MessageButton
        <telethon.tl.custom.messagebutton.MessageButton>`,
        if any.

        Otherwise, it returns `None`.
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
        Returns `buttons` when that property fails (this is rarely needed).
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
        Returns the total button count (sum of all `buttons` rows).
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
    def file(self):
        """
        Returns a `File <telethon.tl.custom.file.File>` wrapping the
        `photo` or `document` in this message. If the media type is different
        (polls, games, none, etc.), this property will be `None`.

        This instance lets you easily access other properties, such as
        `file.id <telethon.tl.custom.file.File.id>`,
        `file.name <telethon.tl.custom.file.File.name>`,
        etc., without having to manually inspect the ``document.attributes``.
        """
        if not self._file:
            media = self.photo or self.document
            if media:
                self._file = File(media)

        return self._file

    @property
    def photo(self):
        """
        The :tl:`Photo` media in this message, if any.

        This will also return the photo for :tl:`MessageService` if its
        action is :tl:`MessageActionChatEditPhoto`, or if the message has
        a web preview with a photo.
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
        The :tl:`Document` media in this message, if any.
        """
        if isinstance(self.media, types.MessageMediaDocument):
            if isinstance(self.media.document, types.Document):
                return self.media.document
        else:
            web = self.web_preview
            if web and isinstance(web.document, types.Document):
                return web.document

    @property
    def web_preview(self):
        """
        The :tl:`WebPage` media in this message, if any.
        """
        if isinstance(self.media, types.MessageMediaWebPage):
            if isinstance(self.media.webpage, types.WebPage):
                return self.media.webpage

    @property
    def audio(self):
        """
        The :tl:`Document` media in this message, if it's an audio file.
        """
        return self._document_by_attribute(types.DocumentAttributeAudio,
                                           lambda attr: not attr.voice)

    @property
    def voice(self):
        """
        The :tl:`Document` media in this message, if it's a voice note.
        """
        return self._document_by_attribute(types.DocumentAttributeAudio,
                                           lambda attr: attr.voice)

    @property
    def video(self):
        """
        The :tl:`Document` media in this message, if it's a video.
        """
        return self._document_by_attribute(types.DocumentAttributeVideo)

    @property
    def video_note(self):
        """
        The :tl:`Document` media in this message, if it's a video note.
        """
        return self._document_by_attribute(types.DocumentAttributeVideo,
                                           lambda attr: attr.round_message)

    @property
    def gif(self):
        """
        The :tl:`Document` media in this message, if it's a "gif".

        "Gif" files by Telegram are normally ``.mp4`` video files without
        sound, the so called "animated" media. However, it may be the actual
        gif format if the file is too large.
        """
        return self._document_by_attribute(types.DocumentAttributeAnimated)

    @property
    def sticker(self):
        """
        The :tl:`Document` media in this message, if it's a sticker.
        """
        return self._document_by_attribute(types.DocumentAttributeSticker)

    @property
    def contact(self):
        """
        The :tl:`MessageMediaContact` in this message, if it's a contact.
        """
        if isinstance(self.media, types.MessageMediaContact):
            return self.media

    @property
    def game(self):
        """
        The :tl:`Game` media in this message, if it's a game.
        """
        if isinstance(self.media, types.MessageMediaGame):
            return self.media.game

    @property
    def geo(self):
        """
        The :tl:`GeoPoint` media in this message, if it has a location.
        """
        if isinstance(self.media, (types.MessageMediaGeo,
                                   types.MessageMediaGeoLive,
                                   types.MessageMediaVenue)):
            return self.media.geo

    @property
    def invoice(self):
        """
        The :tl:`MessageMediaInvoice` in this message, if it's an invoice.
        """
        if isinstance(self.media, types.MessageMediaInvoice):
            return self.media

    @property
    def poll(self):
        """
        The :tl:`MessageMediaPoll` in this message, if it's a poll.
        """
        if isinstance(self.media, types.MessageMediaPoll):
            return self.media

    @property
    def venue(self):
        """
        The :tl:`MessageMediaVenue` in this message, if it's a venue.
        """
        if isinstance(self.media, types.MessageMediaVenue):
            return self.media

    @property
    def dice(self):
        """
        The :tl:`MessageMediaDice` in this message, if it's a dice roll.
        """
        if isinstance(self.media, types.MessageMediaDice):
            return self.media

    @property
    def action_entities(self):
        """
        Returns a list of entities that took part in this action.

        Possible cases for this are :tl:`MessageActionChatAddUser`,
        :tl:`types.MessageActionChatCreate`, :tl:`MessageActionChatDeleteUser`,
        :tl:`MessageActionChatJoinedByLink` :tl:`MessageActionChatMigrateTo`
        and :tl:`MessageActionChannelMigrateFrom`.

        If the action is neither of those, the result will be `None`.
        If some entities could not be retrieved, the list may contain
        some `None` items in it.
        """
        return self._action_entities

    @property
    def via_bot(self):
        """
        The bot :tl:`User` if the message was sent via said bot.

        This will only be present if `via_bot_id` is not `None` and
        the entity is known.
        """
        return self._via_bot

    @property
    def via_input_bot(self):
        """
        Returns the input variant of `via_bot`.
        """
        return self._via_input_bot

    @property
    def reply_to_msg_id(self):
        """
        Returns the message ID this message is replying to, if any.
        This is equivalent to accessing ``.reply_to.reply_to_msg_id``.
        """
        return self.reply_to.reply_to_msg_id if self.reply_to else None

    @property
    def to_id(self):
        """
        Returns the peer to which this message was sent to. This used to exist
        to infer the ``.peer_id``.
        """
        # If the client wasn't set we can't emulate the behaviour correctly,
        # so as a best-effort simply return the chat peer.
        if self._client and not self.out and self.is_private:
            return types.PeerUser(self._client._self_id)

        return self.peer_id

    # endregion Public Properties

    # region Public Methods

    def get_entities_text(self, cls=None):
        """
        Returns a list of ``(markup entity, inner text)``
        (like bold or italics).

        The markup entity is a :tl:`MessageEntity` that represents bold,
        italics, etc., and the inner text is the `str` inside that markup
        entity.

        For example:

        .. code-block:: python

            print(repr(message.text))  # shows: 'Hello **world**!'

            for ent, txt in message.get_entities_text():
                print(ent)  # shows: MessageEntityBold(offset=6, length=5)
                print(txt)  # shows: world

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
        The `Message` that this message is replying to, or `None`.

        The result will be cached after its first use.
        """
        if self._reply_message is None and self._client:
            if not self.reply_to:
                return None

            # Bots cannot access other bots' messages by their ID.
            # However they can access them through replies...
            self._reply_message = await self._client.get_messages(
                await self.get_input_chat() if self.is_channel else None,
                ids=types.InputMessageReplyTo(self.id)
            )
            if not self._reply_message:
                # ...unless the current message got deleted.
                #
                # If that's the case, give it a second chance accessing
                # directly by its ID.
                self._reply_message = await self._client.get_messages(
                    self._input_chat if self.is_channel else None,
                    ids=self.reply_to.reply_to_msg_id
                )

        return self._reply_message

    async def respond(self, *args, **kwargs):
        """
        Responds to the message (not as a reply). Shorthand for
        `telethon.client.messages.MessageMethods.send_message`
        with ``entity`` already set.
        """
        if self._client:
            return await self._client.send_message(
                await self.get_input_chat(), *args, **kwargs)

    async def reply(self, *args, **kwargs):
        """
        Replies to the message (as a reply). Shorthand for
        `telethon.client.messages.MessageMethods.send_message`
        with both ``entity`` and ``reply_to`` already set.
        """
        if self._client:
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
        if self._client:
            kwargs['messages'] = self.id
            kwargs['from_peer'] = await self.get_input_chat()
            return await self._client.forward_messages(*args, **kwargs)

    async def edit(self, *args, **kwargs):
        """
        Edits the message if it's outgoing. Shorthand for
        `telethon.client.messages.MessageMethods.edit_message`
        with both ``entity`` and ``message`` already set.

        Returns
            The edited `Message <telethon.tl.custom.message.Message>`,
            unless `entity` was a :tl:`InputBotInlineMessageID` or :tl:`InputBotInlineMessageID64` in which
            case this method returns a boolean.

        Raises
            ``MessageAuthorRequiredError`` if you're not the author of the
            message but tried editing it anyway.

            ``MessageNotModifiedError`` if the contents of the message were
            not modified at all.

            ``MessageIdInvalidError`` if the ID of the message is invalid
            (the ID itself may be correct, but the message with that ID
            cannot be edited). For example, when trying to edit messages
            with a reply markup (or clear markup) this error will be raised.

        .. note::

            This is different from `client.edit_message
            <telethon.client.messages.MessageMethods.edit_message>`
            and **will respect** the previous state of the message.
            For example, if the message didn't have a link preview,
            the edit won't add one by default, and you should force
            it by setting it to `True` if you want it.

            This is generally the most desired and convenient behaviour,
            and will work for link previews and message buttons.
        """
        if 'link_preview' not in kwargs:
            kwargs['link_preview'] = bool(self.web_preview)

        if 'buttons' not in kwargs:
            kwargs['buttons'] = self.reply_markup

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
        if self._client:
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
        if self._client:
            # Passing the entire message is important, in case it has to be
            # refetched for a fresh file reference.
            return await self._client.download_media(self, *args, **kwargs)

    async def click(self, i=None, j=None,
                    *, text=None, filter=None, data=None, share_phone=None,
                    share_geo=None, password=None):
        """
        Calls :tl:`SendVote` with the specified poll option
        or `button.click <telethon.tl.custom.messagebutton.MessageButton.click>`
        on the specified button.

        Does nothing if the message is not a poll or has no buttons.

        Args:
            i (`int` | `list`):
                Clicks the i'th button or poll option (starting from the index 0).
                For multiple-choice polls, a list with the indices should be used.
                Will ``raise IndexError`` if out of bounds. Example:

                >>> message = ...  # get the message somehow
                >>> # Clicking the 3rd button
                >>> # [button1] [button2]
                >>> # [     button3     ]
                >>> # [button4] [button5]
                >>> await message.click(2)  # index

            j (`int`):
                Clicks the button at position (i, j), these being the
                indices for the (row, column) respectively. Example:

                >>> # Clicking the 2nd button on the 1st row.
                >>> # [button1] [button2]
                >>> # [     button3     ]
                >>> # [button4] [button5]
                >>> await message.click(0, 1)  # (row, column)

                This is equivalent to ``message.buttons[0][1].click()``.

            text (`str` | `callable`):
                Clicks the first button or poll option with the text "text". This may
                also be a callable, like a ``re.compile(...).match``,
                and the text will be passed to it.

                If you need to select multiple options in a poll,
                pass a list of indices to the ``i`` parameter.

            filter (`callable`):
                Clicks the first button or poll option for which the callable
                returns `True`. The callable should accept a single
                `MessageButton <telethon.tl.custom.messagebutton.MessageButton>`
                or `PollAnswer <telethon.tl.types.PollAnswer>` argument.

                If you need to select multiple options in a poll,
                pass a list of indices to the ``i`` parameter.

            data (`bytes`):
                This argument overrides the rest and will not search any
                buttons. Instead, it will directly send the request to
                behave as if it clicked a button with said data. Note
                that if the message does not have this data, it will
                ``raise DataInvalidError``.

            share_phone (`bool` | `str` | tl:`InputMediaContact`):
                When clicking on a keyboard button requesting a phone number
                (:tl:`KeyboardButtonRequestPhone`), this argument must be
                explicitly set to avoid accidentally sharing the number.

                It can be `True` to automatically share the current user's
                phone, a string to share a specific phone number, or a contact
                media to specify all details.

                If the button is pressed without this, `ValueError` is raised.

            share_geo (`tuple` | `list` | tl:`InputMediaGeoPoint`):
                When clicking on a keyboard button requesting a geo location
                (:tl:`KeyboardButtonRequestGeoLocation`), this argument must
                be explicitly set to avoid accidentally sharing the location.

                It must be a `tuple` of `float` as ``(longitude, latitude)``,
                or a :tl:`InputGeoPoint` instance to avoid accidentally using
                the wrong roder.

                If the button is pressed without this, `ValueError` is raised.

            password (`str`):
                When clicking certain buttons (such as BotFather's confirmation
                button to transfer ownership), if your account has 2FA enabled,
                you need to provide your account's password. Otherwise,
                `teltehon.errors.PasswordHashInvalidError` is raised.

            Example:

                .. code-block:: python

                    # Click the first button
                    await message.click(0)

                    # Click some row/column
                    await message.click(row, column)

                    # Click by text
                    await message.click(text='👍')

                    # Click by data
                    await message.click(data=b'payload')

                    # Click on a button requesting a phone
                    await message.click(0, share_phone=True)
        """
        if not self._client:
            return

        if data:
            chat = await self.get_input_chat()
            if not chat:
                return None

            but = types.KeyboardButtonCallback('', data)
            return await MessageButton(self._client, but, chat, None, self.id).click(
                share_phone=share_phone, share_geo=share_geo, password=password)

        if sum(int(x is not None) for x in (i, text, filter)) >= 2:
            raise ValueError('You can only set either of i, text or filter')

        # Finding the desired poll options and sending them
        if self.poll is not None:
            def find_options():
                answers = self.poll.poll.answers
                if i is not None:
                    if utils.is_list_like(i):
                        return [answers[idx].option for idx in i]
                    return [answers[i].option]
                if text is not None:
                    if callable(text):
                        for answer in answers:
                            if text(answer.text):
                                return [answer.option]
                    else:
                        for answer in answers:
                            if answer.text == text:
                                return [answer.option]
                    return

                if filter is not None:
                    for answer in answers:
                        if filter(answer):
                            return [answer.option]
                    return

            options = find_options()
            if options is None:
                options = []
            return await self._client(
                functions.messages.SendVoteRequest(
                    peer=self._input_chat,
                    msg_id=self.id,
                    options=options
                )
            )

        if not await self.get_buttons():
            return  # Accessing the property sets self._buttons[_flat]

        def find_button():
            nonlocal i
            if text is not None:
                if callable(text):
                    for button in self._buttons_flat:
                        if text(button.text):
                            return button
                else:
                    for button in self._buttons_flat:
                        if button.text == text:
                            return button
                return

            if filter is not None:
                for button in self._buttons_flat:
                    if filter(button):
                        return button
                return

            if i is None:
                i = 0
            if j is None:
                return self._buttons_flat[i]
            else:
                return self._buttons[i][j]

        button = find_button()
        if button:
            return await button.click(
                share_phone=share_phone, share_geo=share_geo, password=password)

    async def mark_read(self):
        """
        Marks the message as read. Shorthand for
        `client.send_read_acknowledge()
        <telethon.client.messages.MessageMethods.send_read_acknowledge>`
        with both ``entity`` and ``message`` already set.
        """
        if self._client:
            await self._client.send_read_acknowledge(
                await self.get_input_chat(), max_id=self.id)

    async def pin(self, *, notify=False, pm_oneside=False):
        """
        Pins the message. Shorthand for
        `telethon.client.messages.MessageMethods.pin_message`
        with both ``entity`` and ``message`` already set.
        """
        # TODO Constantly checking if client is a bit annoying,
        #      maybe just make it illegal to call messages from raw API?
        #      That or figure out a way to always set it directly.
        if self._client:
            return await self._client.pin_message(
                await self.get_input_chat(), self.id, notify=notify, pm_oneside=pm_oneside)

    async def unpin(self):
        """
        Unpins the message. Shorthand for
        `telethon.client.messages.MessageMethods.unpin_message`
        with both ``entity`` and ``message`` already set.
        """
        if self._client:
            return await self._client.unpin_message(
                await self.get_input_chat(), self.id)

    # endregion Public Methods

    # region Private Methods

    async def _reload_message(self):
        """
        Re-fetches this message to reload the sender and chat entities,
        along with their input versions.
        """
        if not self._client:
            return

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
        self._via_bot = msg._via_bot
        self._via_input_bot = msg._via_input_bot
        self._forward = msg._forward
        self._action_entities = msg._action_entities

    async def _refetch_sender(self):
        await self._reload_message()

    def _set_buttons(self, chat, bot):
        """
        Helper methods to set the buttons given the input sender and chat.
        """
        if self._client and isinstance(self.reply_markup, (
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
        cannot be found but is needed. Returns `None` if it's not needed.
        """
        if self._client and not isinstance(self.reply_markup, (
                types.ReplyInlineMarkup, types.ReplyKeyboardMarkup)):
            return None

        for row in self.reply_markup.rows:
            for button in row.buttons:
                if isinstance(button, types.KeyboardButtonSwitchInline):
                    # no via_bot_id means the bot sent the message itself (#1619)
                    if button.same_peer or not self.via_bot_id:
                        bot = self.input_sender
                        if not bot:
                            raise ValueError('No input sender')
                        return bot
                    else:
                        try:
                            return self._client._mb_entity_cache.get(
                                utils.resolve_id(self.via_bot_id)[0])._as_input_peer()
                        except AttributeError:
                            raise ValueError('No input sender') from None

    def _document_by_attribute(self, kind, condition=None):
        """
        Helper method to return the document only if it has an attribute
        that's an instance of the given kind, and passes the condition.
        """
        doc = self.document
        if doc:
            for attr in doc.attributes:
                if isinstance(attr, kind):
                    if not condition or condition(attr):
                        return doc
                    return None

    # endregion Private Methods
