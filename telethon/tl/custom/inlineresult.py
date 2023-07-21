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
    # tdlib types are the following (InlineQueriesManager::answer_inline_query @ 1a4a834):
    # gif, article, audio, contact, file, geo, photo, sticker, venue, video, voice
    #
    # However, those documented in https://core.telegram.org/bots/api#inline-mode are different.
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

    def __init__(self, client, original, query_id=None, *, entity=None):
        self._client = client
        self.result = original
        self._query_id = query_id
        self._entity = entity

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
        The title for this inline result. It may be `None`.
        """
        return self.result.title

    @property
    def description(self):
        """
        The description for this inline result. It may be `None`.
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
        """
        Returns either the :tl:`WebDocument` thumbnail for
        normal results or the :tl:`Photo` for media results.
        """
        if isinstance(self.result, types.BotInlineResult):
            return self.result.thumb
        elif isinstance(self.result, types.BotInlineMediaResult):
            return self.result.photo

    @property
    def document(self):
        """
        Returns either the :tl:`WebDocument` content for
        normal results or the :tl:`Document` for media results.
        """
        if isinstance(self.result, types.BotInlineResult):
            return self.result.content
        elif isinstance(self.result, types.BotInlineMediaResult):
            return self.result.document

    async def click(self, entity=None, reply_to=None, comment_to=None,
                    silent=False, clear_draft=False, hide_via=False,
                    background=None):
        """
        Clicks this result and sends the associated `message`.

        Args:
            entity (`entity`):
                The entity to which the message of this result should be sent.

            reply_to (`int` | `Message <telethon.tl.custom.message.Message>`, optional):
                If present, the sent message will reply to this ID or message.

            comment_to (`int` | `Message <telethon.tl.custom.message.Message>`, optional):
                Similar to ``reply_to``, but replies in the linked group of a
                broadcast channel instead (effectively leaving a "comment to"
                the specified message).

            silent (`bool`, optional):
                Whether the message should notify people with sound or not.
                Defaults to `False` (send with a notification sound unless
                the person has the chat muted). Set it to `True` to alter
                this behaviour.

            clear_draft (`bool`, optional):
                Whether the draft should be removed after sending the
                message from this result or not. Defaults to `False`.

            hide_via (`bool`, optional):
                Whether the "via @bot" should be hidden or not.
                Only works with certain bots (like @bing or @gif).

            background (`bool`, optional):
                Whether the message should be send in background.

        """
        if entity:
            entity = await self._client.get_input_entity(entity)
        elif self._entity:
            entity = self._entity
        else:
            raise ValueError('You must provide the entity where the result should be sent to')

        if comment_to:
            entity, reply_id = await self._client._get_comment_data(entity, comment_to)
        else:
            reply_id = None if reply_to is None else utils.get_message_id(reply_to)

        req = functions.messages.SendInlineBotResultRequest(
            peer=entity,
            query_id=self._query_id,
            id=self.result.id,
            silent=silent,
            background=background,
            clear_draft=clear_draft,
            hide_via=hide_via,
            reply_to=None if reply_id is None else types.InputReplyToMessage(reply_id)
        )
        return self._client._get_response_message(
            req, await self._client(req), entity)

    async def download_media(self, *args, **kwargs):
        """
        Downloads the media in this result (if there is a document, the
        document will be downloaded; otherwise, the photo will if present).

        This is a wrapper around `client.download_media
        <telethon.client.downloads.DownloadMethods.download_media>`.
        """
        if self.document or self.photo:
            return await self._client.download_media(
                self.document or self.photo, *args, **kwargs)
