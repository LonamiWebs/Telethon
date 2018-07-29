from .. import types, functions
from ... import utils


class InlineResult:
    """
    Custom class that encapsulates a bot inline result providing
    an abstraction to easily access some commonly needed features
    (such as clicking a result to select it).

    Attributes:

        result (:tl:`BotInlineResult`):
            The original :tl:`BotInlineResult` object.
    """
    ARTICLE = 'article'
    PHOTO = 'photo'
    GIF = 'gif'
    VIDEO = 'video'
    VIDEO_GIF = 'mpeg4_gif'
    AUDIO = 'audio'
    DOCUMENT = 'document'
    LOCATION = 'location'
    VENUE = 'venue'
    CONTACT = 'contact'
    GAME = 'game'

    def __init__(self, client, original, query_id=None):
        self._client = client
        self.result = original
        self._query_id = query_id

    @property
    def type(self):
        """
        The always-present type of this result. It will be one of:
        ``'article'``, ``'photo'``, ``'gif'``, ``'mpeg4_gif'``, ``'video'``,
        ``'audio'``, ``'voice'``, ``'document'``, ``'location'``, ``'venue'``,
        ``'contact'``, ``'game'``.

        You can access all of these constants through `InlineResult`,
        such as `InlineResult.ARTICLE`, `InlineResult.VIDEO_GIF`, etc.
        """
        return self.result.type

    @property
    def message(self):
        """
        The always-present :tl:`BotInlineMessage` that
        will be sent if `click` is called on this result.
        """
        return self.result.send_message

    @property
    def title(self):
        """
        The title for this inline result. It may be ``None``.
        """
        return self.result.title

    @property
    def description(self):
        """
        The description for this inline result. It may be ``None``.
        """
        return self.result.description

    @property
    def url(self):
        """
        The URL present in this inline results. If you want to "click"
        this URL to open it in your browser, you should use Python's
        `webbrowser.open(url)` for such task.
        """
        if isinstance(self.result, types.BotInlineResult):
            return self.result.url

    @property
    def photo(self):
        # TODO Document - how to deal with web media vs. normal?
        if isinstance(self.result, types.BotInlineResult):
            return self.result.thumb
        elif isinstance(self.result, types.BotInlineMediaResult):
            return self.result.photo

    @property
    def document(self):
        # TODO Document - how to deal with web media vs. normal?
        if isinstance(self.result, types.BotInlineResult):
            return self.result.content
        elif isinstance(self.result, types.BotInlineMediaResult):
            return self.result.document

    async def click(self, entity, reply_to=None,
                    silent=False, clear_draft=False):
        """
        Clicks this result and sends the associated `message`.

        Args:
            entity (`entity`):
                The entity to which the message of this result should be sent.

            reply_to (`int` | :tl:`Message`, optional):
                If present, the sent message will reply to this ID or message.

            silent (`bool`, optional):
                If ``True``, the sent message will not notify the user(s).

            clear_draft (`bool`, optional):
                Whether the draft should be removed after sending the
                message from this result or not. Defaults to ``False``.
        """
        entity = await self._client.get_input_entity(entity)
        reply_id = None if reply_to is None else utils.get_message_id(reply_to)
        req = self._client(functions.messages.SendInlineBotResultRequest(
            peer=entity,
            query_id=self._query_id,
            id=self.result.id,
            silent=silent,
            clear_draft=clear_draft,
            reply_to_msg_id=reply_id
        ))
        return self._client._get_response_message(req, await req, entity)

    async def download_photo(self):
        """
        Downloads the media in `photo` if any and returns the download path.
        """
        pass

    async def download_document(self):
        """
        Downloads the media in `document` if any and returns the download path.
        """
        pass
