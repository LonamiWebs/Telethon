from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
import mimetypes
from .chatgetter import ChatGetter
from .sendergetter import SenderGetter
from .messagebutton import MessageButton
from .forward import Forward
from .file import File
from .inputfile import InputFile
from .inputmessage import InputMessage
from .button import build_reply_markup
from ..._misc import utils, helpers, tlobject, markdown, html
from ... import _tl, _misc


if TYPE_CHECKING:
    from ..._misc import hints


def _fwd(field, doc):
    def fget(self):
        return getattr(self._message, field, None)

    def fset(self, value):
        object.__setattr__(self._message, field, value)

    return property(fget, fset, None, doc)


class _UninitClient:
    def __getattribute__(self, attr):
        raise ValueError('this Message instance does not come from a chat and cannot be used')


# TODO Figure out a way to have the code generator error on missing fields
# Maybe parsing the init function alone if that's possible.
class Message(ChatGetter, SenderGetter):
    """
    Represents a :tl:`Message` (or :tl:`MessageService`) from the API.

    Remember that this class implements `ChatGetter
    <telethon.tl.custom.chatgetter.ChatGetter>` and `SenderGetter
    <telethon.tl.custom.sendergetter.SenderGetter>` which means you
    have access to all their sender and chat properties and methods.

    You can also create your own instance of this type to customize how a
    message should be sent (rather than just plain text). For example, you
    can create an instance with a text to be used for the caption of an audio
    file with a certain performer, duration and thumbnail. However, most
    properties and methods won't work (since messages you create have not yet
    been sent).

    Manually-created instances of this message cannot be responded to, edited,
    and so on, because the message needs to first be sent for those to make sense.
    """

    # region Forwarded properties

    out = _fwd('out', """
        Whether the message is outgoing (i.e. you sent it from
        another session) or incoming (i.e. someone else sent it).

        Note that messages in your own chat are always incoming,
        but this member will be `True` if you send a message
        to your own chat. Messages you forward to your chat are
        *not* considered outgoing, just like official clients
        display them.
    """)

    mentioned = _fwd('mentioned', """
        Whether you were mentioned in this message or not.
        Note that replies to your own messages also count
        as mentions.
    """)

    media_unread = _fwd('media_unread', """
        Whether you have read the media in this message
        or not, e.g. listened to the voice note media.
    """)

    silent = _fwd('silent', """
        Whether the message should notify people with sound or not.
        Previously used in channels, but since 9 August 2019, it can
        also be `used in private chats
        <https://telegram.org/blog/silent-messages-slow-mode>`_.
    """)

    post = _fwd('post', """
        Whether this message is a post in a broadcast
        channel or not.
    """)

    from_scheduled = _fwd('from_scheduled', """
        Whether this message was originated from a previously-scheduled
        message or not.
    """)

    legacy = _fwd('legacy', """
        Whether this is a legacy message or not.
    """)

    edit_hide = _fwd('edit_hide', """
        Whether the edited mark of this message is edited
        should be hidden (e.g. in GUI clients) or shown.
    """)

    pinned = _fwd('pinned', """
        Whether this message is currently pinned or not.
    """)

    id = _fwd('id', """
        The ID of this message. This field is *always* present.
        Any other member is optional and may be `None`.
    """)

    from_id = _fwd('from_id', """
        The peer who sent this message, which is either
        :tl:`PeerUser`, :tl:`PeerChat` or :tl:`PeerChannel`.
        This value will be `None` for anonymous messages.
    """)

    peer_id = _fwd('peer_id', """
        The peer to which this message was sent, which is either
        :tl:`PeerUser`, :tl:`PeerChat` or :tl:`PeerChannel`. This
        will always be present except for empty messages.
    """)

    fwd_from = _fwd('fwd_from', """
        The original forward header if this message is a forward.
        You should probably use the `forward` property instead.
    """)

    via_bot_id = _fwd('via_bot_id', """
        The ID of the bot used to send this message
        through its inline mode (e.g. "via @like").
    """)

    reply_to = _fwd('reply_to', """
        The original reply header if this message is replying to another.
    """)

    date = _fwd('date', """
        The UTC+0 `datetime` object indicating when this message
        was sent. This will always be present except for empty
        messages.
    """)

    message = _fwd('message', """
        The string text of the message for `Message
        <telethon.tl.custom.message.Message>` instances,
        which will be `None` for other types of messages.
    """)

    @property
    def media(self):
        """
        The media sent with this message if any (such as
        photos, videos, documents, gifs, stickers, etc.).

        You may want to access the `photo`, `document`
        etc. properties instead.

        If the media was not present or it was :tl:`MessageMediaEmpty`,
        this member will instead be `None` for convenience.
        """
        try:
            media = self._message.media
        except AttributeError:
            return None

        return None if media.CONSTRUCTOR_ID == 0x3ded6320 else media

    @media.setter
    def media(self, value):
        try:
            self._message.media = value
        except AttributeError:
            pass

    reply_markup = _fwd('reply_markup', """
        The reply markup for this message (which was sent
        either via a bot or by a bot). You probably want
        to access `buttons` instead.
    """)

    entities = _fwd('entities', """
        The list of markup entities in this message,
        such as bold, italics, code, hyperlinks, etc.
    """)

    views = _fwd('views', """
        The number of views this message from a broadcast
        channel has. This is also present in forwards.
    """)

    forwards = _fwd('forwards', """
        The number of times this message has been forwarded.
    """)

    noforwards = _fwd('noforwards', """
        does the message was sent with noforwards restriction.
    """)

    replies = _fwd('replies', """
        The number of times another message has replied to this message.
    """)

    edit_date = _fwd('edit_date', """
        The date when this message was last edited.
    """)

    post_author = _fwd('post_author', """
        The display name of the message sender to
        show in messages sent to broadcast channels.
    """)

    grouped_id = _fwd('grouped_id', """
        If this message belongs to a group of messages
        (photo albums or video albums), all of them will
        have the same value here.""")

    restriction_reason = _fwd('restriction_reason', """
        An optional list of reasons why this message was restricted.
        If the list is `None`, this message has not been restricted.
    """)

    reactions = _fwd('reactions', """
        emoji reactions attached to the message.
    """)

    ttl_period = _fwd('ttl_period', """
        The Time To Live period configured for this message.
        The message should be erased from wherever it's stored (memory, a
        local database, etc.) when
        ``datetime.now() > message.date + timedelta(seconds=message.ttl_period)``.
    """)

    action = _fwd('action', """
        The message action object of the message for :tl:`MessageService`
        instances, which will be `None` for other types of messages.
    """)

    # endregion

    # region Initialization

    def __init__(
            self,
            text: str = None,
            *,
            # Formatting
            markdown: str = None,
            html: str = None,
            formatting_entities: list = None,
            link_preview: bool = (),
            # Media
            file: 'Optional[hints.FileLike]' = None,
            file_name: str = None,
            mime_type: str = None,
            thumb: str = False,
            force_file: bool = False,
            file_size: int = None,
            # Media attributes
            duration: int = None,
            width: int = None,
            height: int = None,
            title: str = None,
            performer: str = None,
            supports_streaming: bool = False,
            video_note: bool = False,
            voice_note: bool = False,
            waveform: bytes = None,
            # Additional parametrization
            silent: bool = False,
            buttons: list = None,
            ttl: int = None,
    ):
        """
        The input parameters when creating a new message for sending are:

        :param text: The message text (also known as caption when including media).
        This will be parsed according to the default parse mode, which can be changed with
        ``set_default_parse_mode``.

        By default it's markdown if the ``markdown-it-py`` package is installed, or none otherwise.
        Cannot be used in conjunction with ``text`` or ``html``.

        :param markdown: Sets the text, but forces the parse mode to be markdown.
        Cannot be used in conjunction with ``text`` or ``html``.

        :param html: Sets the text, but forces the parse mode to be HTML.
        Cannot be used in conjunction with ``text`` or ``markdown``.

        :param formatting_entities: Manually specifies the formatting entities.
        Neither of ``text``, ``markdown`` or ``html`` will be processed.

        :param link_preview: Whether to include a link preview media in the message.
        The default is to show it, but this can be changed with ``set_default_link_preview``.
        Has no effect if the message contains other media (such as photos).

        :param file: Send a file. The library will automatically determine whether to send the
        file as a photo or as a document based on the extension. You can force a specific type
        by using ``photo`` or ``document`` instead. The file can be one of:

        * A local file path to an in-disk file. The file name will default to the path's base name.

        * A `bytes` byte array with the file's data to send (for example, by using
          ``text.encode('utf-8')``). A default file name will be used.

        * A bytes `io.IOBase` stream over the file to send (for example, by using
          ``open(file, 'rb')``). Its ``.name`` property will be used for the file name, or a
          default if it doesn't have one.

        * An external URL to a file over the internet. This will send the file as "external"
          media, and Telegram is the one that will fetch the media and send it. This means
          the library won't download the file to send it first, but Telegram may fail to access
          the media. The URL must start with either ``'http://'`` or ``https://``.

        * A handle to an existing file (for example, if you sent a message with media before,
          you can use its ``message.media`` as a file here).

        * A :tl:`InputMedia` instance. For example, if you want to send a dice use
          :tl:`InputMediaDice`, or if you want to send a contact use :tl:`InputMediaContact`.

        :param file_name: Forces a specific file name to be used, rather than an automatically
        determined one. Has no effect with previously-sent media.

        :param mime_type: Sets a fixed mime type for the file, rather than having the library
        guess it from the final file name. Useful when an URL does not contain an extension.
        The mime-type will be used to determine which media attributes to include (for instance,
        whether to send a video, an audio, or a photo).

        * For an image to contain an image size, you must specify width and height.
        * For an audio, you must specify the duration.
        * For a video, you must specify width, height and duration.

        :param thumb: A file to be used as the document's thumbnail. Only has effect on uploaded
        documents.

        :param force_file: Forces whatever file was specified to be sent as a file.
        Has no effect with previously-sent media.

        :param file_size: The size of the file to be uploaded if it needs to be uploaded, which
        will be determined automatically if not specified. If the file size can't be determined
        beforehand, the entire file will be read in-memory to find out how large it is. Telegram
        requires the file size to be known before-hand (except for external media).

        :param duration: Specifies the duration, in seconds, of the audio or video file. Only has
        effect on uploaded documents.

        :param width: Specifies the photo or video width, in pixels. Only has an effect on uploaded
        documents.

        :param height: Specifies the photo or video height, in pixels. Only has an effect on
        uploaded documents.

        :param title: Specifies the title of the song being sent. Only has effect on uploaded
        documents. You must specify the audio duration.

        :param performer: Specifies the performer of the song being sent. Only has effect on
        uploaded documents. You must specify the audio duration.

        :param supports_streaming: Whether the video has been recorded in such a way that it
        supports streaming. Note that not all format can support streaming. Only has effect on
        uploaded documents. You must specify the video duration, width and height.

        :param video_note: Whether the video should be a "video note" and render inside a circle.
        Only has effect on uploaded documents. You must specify the video duration, width and
        height.

        :param voice_note: Whether the audio should be a "voice note" and render with a waveform.
        Only has effect on uploaded documents. You must specify the audio duration.

        :param waveform: The waveform. You must specify the audio duration.

        :param silent: Whether the message should notify people with sound or not. By default, a
        notification with sound is sent unless the person has the chat muted).

        :param buttons: The matrix (list of lists), column list or button to be shown after
        sending the message. This parameter will only work if you have signed in as a bot.

        :param schedule: If set, the message won't send immediately, and instead it will be
        scheduled to be automatically sent at a later time.

        :param ttl: The Time-To-Live of the file (also known as "self-destruct timer" or
        "self-destructing media"). If set, files can only be viewed for a short period of time
        before they disappear from the message history automatically.

        The value must be at least 1 second, and at most 60 seconds, otherwise Telegram will
        ignore this parameter.

        Not all types of media can be used with this parameter, such as text documents, which
        will fail with ``TtlMediaInvalidError``.
        """
        self._message = InputMessage(
            text=text,
            markdown=markdown,
            html=html,
            formatting_entities=formatting_entities,
            link_preview=link_preview,
            file =file,
            file_name=file_name,
            mime_type=mime_type,
            thumb=thumb,
            force_file=force_file,
            file_size=file_size,
            duration=duration,
            width=width,
            height=height,
            title=title,
            performer=performer,
            supports_streaming=supports_streaming,
            video_note=video_note,
            voice_note=voice_note,
            waveform=waveform,
            silent=silent,
            buttons=buttons,
            ttl=ttl,
        )
        self._client = _UninitClient()

    @classmethod
    def _new(cls, client, message, entities, input_chat):
        self = cls.__new__(cls)

        sender_id = None
        if isinstance(message, _tl.Message):
            if message.from_id is not None:
                sender_id = utils.get_peer_id(message.from_id)

        self = cls.__new__(cls)
        self._client = client
        self._sender = entities.get(_tl.PeerUser(update.user_id))
        self._chat = entities.get(_tl.PeerUser(update.user_id))
        self._message = message

        # Convenient storage for custom functions
        self._file = None
        self._reply_message = None
        self._buttons = None
        self._buttons_flat = None
        self._buttons_count = None
        self._via_bot = None
        self._via_input_bot = None
        self._action_entities = None
        self._linked_chat = None
        self._forward = None

        # Make messages sent to ourselves outgoing unless they're forwarded.
        # This makes it consistent with official client's appearance.
        if self.peer_id == _tl.PeerUser(client._session_state.user_id) and not self.fwd_from:
            self.out = True

        self._sender, self._input_sender = utils._get_entity_pair(self.sender_id, entities)

        self._chat, self._input_chat = utils._get_entity_pair(self.chat_id, entities)

        if input_chat:  # This has priority
            self._input_chat = input_chat

        if self.via_bot_id:
            self._via_bot, self._via_input_bot = utils._get_entity_pair(self.via_bot_id, entities)

        if self.fwd_from:
            self._forward = Forward(self._client, self.fwd_from, entities)

        if self.action:
            if isinstance(self.action, (_tl.MessageActionChatAddUser,
                                        _tl.MessageActionChatCreate)):
                self._action_entities = [entities.get(i)
                                         for i in self.action.users]
            elif isinstance(self.action, _tl.MessageActionChatDeleteUser):
                self._action_entities = [entities.get(self.action.user_id)]
            elif isinstance(self.action, _tl.MessageActionChatJoinedByLink):
                self._action_entities = [entities.get(self.action.inviter_id)]
            elif isinstance(self.action, _tl.MessageActionChatMigrateTo):
                self._action_entities = [entities.get(utils.get_peer_id(
                    _tl.PeerChannel(self.action.channel_id)))]
            elif isinstance(
                    self.action, _tl.MessageActionChannelMigrateFrom):
                self._action_entities = [entities.get(utils.get_peer_id(
                    _tl.PeerChat(self.action.chat_id)))]

        if self.replies and self.replies.channel_id:
            self._linked_chat = entities.get(utils.get_peer_id(
                    _tl.PeerChannel(self.replies.channel_id)))

        return self


    @staticmethod
    def set_default_parse_mode(mode):
        """
        Change the default parse mode when creating messages. The ``mode`` can be:

        * ``None``, to disable parsing.
        * A string equal to ``'md'`` or ``'markdown`` for parsing with commonmark,
          ``'htm'`` or ``'html'`` for parsing HTML.
        * A ``callable``, which accepts a ``str`` as input and returns a tuple of
          ``(parsed str, formatting entities)``. Obtaining formatted text from a message in
          this setting is not supported and will instead return the plain text.
        * A ``tuple`` of two ``callable``. The first must accept a ``str`` as input and return
          a tuple of ``(parsed str, list of formatting entities)``. The second must accept two
          parameters, a parsed ``str`` and a ``list`` of formatting entities, and must return
          an "unparsed" ``str``.

        If it's not one of these values or types, the method fails accordingly.
        """
        InputMessage._default_parse_mode = utils.sanitize_parse_mode(mode)

    @classmethod
    def set_default_link_preview(cls, enabled):
        """
        Change the default value for link preview (either ``True`` or ``False``).
        """
        InputMessage._default_link_preview = enabled

    # endregion Initialization

    # region Public Properties

    @property
    def client(self):
        """
        Returns the `TelegramClient <telethon.client.telegramclient.TelegramClient>`
        which returned this message from a friendly method. It won't be there if you
        invoke raw API methods manually (because those return the original :tl:`Message`,
        not this class).
        """
        return self._client

    @property
    def text(self):
        """
        The message text, formatted using the default parse mode.
        Will be `None` for :tl:`MessageService`.
        """
        return InputMessage._default_parse_mode[1](self.message, self.entities)

    @text.setter
    def text(self, value):
        self.message, self.entities = InputMessage._default_parse_mode[0](value)

    @property
    def raw_text(self):
        """
        The plain message text, ignoring any formatting. Will be `None` for :tl:`MessageService`.

        Setting a value to this field will erase the `entities`, unlike changing the `message` member.
        """
        return self.message

    @raw_text.setter
    def raw_text(self, value):
        self.message = value
        self.entities = []

    @property
    def markdown(self):
        """
        The message text, formatted using markdown. Will be `None` for :tl:`MessageService`.
        """
        return markdown.unparse(self.message, self.entities)

    @markdown.setter
    def markdown(self, value):
        self.message, self.entities = markdown.parse(value)

    @property
    def html(self):
        """
        The message text, formatted using HTML. Will be `None` for :tl:`MessageService`.
        """
        return html.unparse(self.message, self.entities)

    @html.setter
    def html(self, value):
        self.message, self.entities = html.parse(value)

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
                    _tl.ReplyInlineMarkup, _tl.ReplyKeyboardMarkup)):
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
        if isinstance(self.media, _tl.MessageMediaPhoto):
            if isinstance(self.media.photo, _tl.Photo):
                return self.media.photo
        elif isinstance(self.action, _tl.MessageActionChatEditPhoto):
            return self.action.photo
        else:
            web = self.web_preview
            if web and isinstance(web.photo, _tl.Photo):
                return web.photo

    @property
    def document(self):
        """
        The :tl:`Document` media in this message, if any.
        """
        if isinstance(self.media, _tl.MessageMediaDocument):
            if isinstance(self.media.document, _tl.Document):
                return self.media.document
        else:
            web = self.web_preview
            if web and isinstance(web.document, _tl.Document):
                return web.document

    @property
    def web_preview(self):
        """
        The :tl:`WebPage` media in this message, if any.
        """
        if isinstance(self.media, _tl.MessageMediaWebPage):
            if isinstance(self.media.webpage, _tl.WebPage):
                return self.media.webpage

    @property
    def audio(self):
        """
        The :tl:`Document` media in this message, if it's an audio file.
        """
        return self._document_by_attribute(_tl.DocumentAttributeAudio,
                                           lambda attr: not attr.voice)

    @property
    def voice(self):
        """
        The :tl:`Document` media in this message, if it's a voice note.
        """
        return self._document_by_attribute(_tl.DocumentAttributeAudio,
                                           lambda attr: attr.voice)

    @property
    def video(self):
        """
        The :tl:`Document` media in this message, if it's a video.
        """
        return self._document_by_attribute(_tl.DocumentAttributeVideo)

    @property
    def video_note(self):
        """
        The :tl:`Document` media in this message, if it's a video note.
        """
        return self._document_by_attribute(_tl.DocumentAttributeVideo,
                                           lambda attr: attr.round_message)

    @property
    def gif(self):
        """
        The :tl:`Document` media in this message, if it's a "gif".

        "Gif" files by Telegram are normally ``.mp4`` video files without
        sound, the so called "animated" media. However, it may be the actual
        gif format if the file is too large.
        """
        return self._document_by_attribute(_tl.DocumentAttributeAnimated)

    @property
    def sticker(self):
        """
        The :tl:`Document` media in this message, if it's a sticker.
        """
        return self._document_by_attribute(_tl.DocumentAttributeSticker)

    @property
    def contact(self):
        """
        The :tl:`MessageMediaContact` in this message, if it's a contact.
        """
        if isinstance(self.media, _tl.MessageMediaContact):
            return self.media

    @property
    def game(self):
        """
        The :tl:`Game` media in this message, if it's a game.
        """
        if isinstance(self.media, _tl.MessageMediaGame):
            return self.media.game

    @property
    def geo(self):
        """
        The :tl:`GeoPoint` media in this message, if it has a location.
        """
        if isinstance(self.media, (_tl.MessageMediaGeo,
                                   _tl.MessageMediaGeoLive,
                                   _tl.MessageMediaVenue)):
            return self.media.geo

    @property
    def invoice(self):
        """
        The :tl:`MessageMediaInvoice` in this message, if it's an invoice.
        """
        if isinstance(self.media, _tl.MessageMediaInvoice):
            return self.media

    @property
    def poll(self):
        """
        The :tl:`MessageMediaPoll` in this message, if it's a poll.
        """
        if isinstance(self.media, _tl.MessageMediaPoll):
            return self.media

    @property
    def venue(self):
        """
        The :tl:`MessageMediaVenue` in this message, if it's a venue.
        """
        if isinstance(self.media, _tl.MessageMediaVenue):
            return self.media

    @property
    def dice(self):
        """
        The :tl:`MessageMediaDice` in this message, if it's a dice roll.
        """
        if isinstance(self.media, _tl.MessageMediaDice):
            return self.media

    @property
    def action_entities(self):
        """
        Returns a list of entities that took part in this action.

        Possible cases for this are :tl:`MessageActionChatAddUser`,
        :tl:`_tl.MessageActionChatCreate`, :tl:`MessageActionChatDeleteUser`,
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
        if not self.out and self.chat.is_user:
            return _tl.PeerUser(self._client._session_state.user_id)

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
        if self._reply_message is None:
            if not self.reply_to:
                return None

            # Bots cannot access other bots' messages by their ID.
            # However they can access them through replies...
            self._reply_message = await self._client.get_messages(
                self.chat,
                ids=_tl.InputMessageReplyTo(self.id)
            )
            if not self._reply_message:
                # ...unless the current message got deleted.
                #
                # If that's the case, give it a second chance accessing
                # directly by its ID.
                self._reply_message = await self._client.get_messages(
                    self.chat,
                    ids=self.reply_to.reply_to_msg_id
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
                or `PollAnswer <telethon.tl._tl.PollAnswer>` argument.

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
        if data:
            chat = await self.get_input_chat()
            if not chat:
                return None

            but = _tl.KeyboardButtonCallback('', data)
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
                _tl.fn.messages.SendVote(
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
        `client.mark_read()
        <telethon.client.messages.MessageMethods.mark_read>`
        with both ``entity`` and ``message`` already set.
        """
        await self._client.mark_read(
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
        return await self._client.pin_message(
            await self.get_input_chat(), self.id, notify=notify, pm_oneside=pm_oneside)

    async def unpin(self):
        """
        Unpins the message. Shorthand for
        `telethon.client.messages.MessageMethods.unpin_message`
        with both ``entity`` and ``message`` already set.
        """
        return await self._client.unpin_message(
            await self.get_input_chat(), self.id)

    async def react(self, reaction=None):
        """
        Reacts on the given message. Shorthand for
        `telethon.client.messages.MessageMethods.send_reaction`
        with both ``entity`` and ``message`` already set.
        """
        if self._client:
            return await self._client.send_reaction(
                await self.get_input_chat(),
                self.id,
                reaction
            )

    # endregion Public Methods

    # region Private Methods

    def _as_input(self):
        if isinstance(self._message, InputMessage):
            return self._message

        return InputMessage(
            text=self.message,
            formatting_entities=self.entities,
            file=self.media,
            silent=self.silent,
            buttons=self.reply_markup,
        )

    async def _reload_message(self):
        """
        Re-fetches this message to reload the sender and chat entities,
        along with their input versions.
        """
        try:
            msg = await self._client.get_messages(self.chat, ids=self.id)
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

    def _set_buttons(self, chat, bot):
        """
        Helper methods to set the buttons given the input sender and chat.
        """
        if isinstance(self.reply_markup, (
                _tl.ReplyInlineMarkup, _tl.ReplyKeyboardMarkup)):
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
        if not isinstance(self.reply_markup, (
                _tl.ReplyInlineMarkup, _tl.ReplyKeyboardMarkup)):
            return None

        for row in self.reply_markup.rows:
            for button in row.buttons:
                if isinstance(button, _tl.KeyboardButtonSwitchInline):
                    # no via_bot_id means the bot sent the message itself (#1619)
                    if button.same_peer or not self.via_bot_id:
                        bot = self.input_sender
                        if not bot:
                            raise ValueError('No input sender')
                        return bot
                    else:
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

    def to_dict(self):
        return self._message.to_dict()

    def __repr__(self):
        return helpers.pretty_print(self)

    def __str__(self):
        return helpers.pretty_print(self, max_depth=2)

    def stringify(self):
        return helpers.pretty_print(self, indent=0)
