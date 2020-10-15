import hashlib

from .. import functions, types
from ... import utils

_TYPE_TO_MIMES = {
    'gif': ['image/gif'],  # 'video/mp4' too, but that's used for video
    'article': ['text/html'],
    'audio': ['audio/mpeg'],
    'contact': [],
    'file': ['application/pdf', 'application/zip'],  # actually any
    'geo': [],
    'photo': ['image/jpeg'],
    'sticker': ['image/webp', 'application/x-tgsticker'],
    'venue': [],
    'video': ['video/mp4'],  # tdlib includes text/html for some reason
    'voice': ['audio/ogg'],
}


class InlineBuilder:
    """
    Helper class to allow defining `InlineQuery
    <telethon.events.inlinequery.InlineQuery>` ``results``.

    Common arguments to all methods are
    explained here to avoid repetition:

        text (`str`, optional):
            If present, the user will send a text
            message with this text upon being clicked.

        link_preview (`bool`, optional):
            Whether to show a link preview in the sent
            text message or not.

        geo (:tl:`InputGeoPoint`, :tl:`GeoPoint`, :tl:`InputMediaVenue`, :tl:`MessageMediaVenue`, optional):
            If present, it may either be a geo point or a venue.

        period (int, optional):
            The period in seconds to be used for geo points.

        contact (:tl:`InputMediaContact`, :tl:`MessageMediaContact`, optional):
            If present, it must be the contact information to send.

        game (`bool`, optional):
            May be `True` to indicate that the game will be sent.

        buttons (`list`, `custom.Button <telethon.tl.custom.button.Button>`, :tl:`KeyboardButton`, optional):
            Same as ``buttons`` for `client.send_message()
            <telethon.client.messages.MessageMethods.send_message>`.

        parse_mode (`str`, optional):
            Same as ``parse_mode`` for `client.send_message()
            <telethon.client.messageparse.MessageParseMethods.parse_mode>`.

        id (`str`, optional):
            The string ID to use for this result. If not present, it
            will be the SHA256 hexadecimal digest of converting the
            created :tl:`InputBotInlineResult` with empty ID to ``bytes()``,
            so that the ID will be deterministic for the same input.

            .. note::

                If two inputs are exactly the same, their IDs will be the same
                too. If you send two articles with the same ID, it will raise
                ``ResultIdDuplicateError``. Consider giving them an explicit
                ID if you need to send two results that are the same.
    """
    def __init__(self, client):
        self._client = client

    # noinspection PyIncorrectDocstring
    async def article(
            self, title, description=None,
            *, url=None, thumb=None, content=None,
            id=None, text=None, parse_mode=(), link_preview=True,
            geo=None, period=60, contact=None, game=False, buttons=None
    ):
        """
        Creates new inline result of article type.

        Args:
            title (`str`):
                The title to be shown for this result.

            description (`str`, optional):
                Further explanation of what this result means.

            url (`str`, optional):
                The URL to be shown for this result.

            thumb (:tl:`InputWebDocument`, optional):
                The thumbnail to be shown for this result.
                For now it has to be a :tl:`InputWebDocument` if present.

            content (:tl:`InputWebDocument`, optional):
                The content to be shown for this result.
                For now it has to be a :tl:`InputWebDocument` if present.

        Example:
            .. code-block:: python

                results = [
                    # Option with title and description sending a message.
                    builder.article(
                        title='First option',
                        description='This is the first option',
                        text='Text sent after clicking this option',
                    ),
                    # Option with title URL to be opened when clicked.
                    builder.article(
                        title='Second option',
                        url='https://example.com',
                        text='Text sent if the user clicks the option and not the URL',
                    ),
                    # Sending a message with buttons.
                    # You can use a list or a list of lists to include more buttons.
                    builder.article(
                        title='Third option',
                        text='Text sent with buttons below',
                        buttons=Button.url('https://example.com'),
                    ),
                ]
        """
        # TODO Does 'article' work always?
        # article, photo, gif, mpeg4_gif, video, audio,
        # voice, document, location, venue, contact, game
        result = types.InputBotInlineResult(
            id=id or '',
            type='article',
            send_message=await self._message(
                text=text, parse_mode=parse_mode, link_preview=link_preview,
                geo=geo, period=period,
                contact=contact,
                game=game,
                buttons=buttons
            ),
            title=title,
            description=description,
            url=url,
            thumb=thumb,
            content=content
        )
        if id is None:
            result.id = hashlib.sha256(bytes(result)).hexdigest()

        return result

    # noinspection PyIncorrectDocstring
    async def photo(
            self, file, *, id=None, include_media=True,
            text=None, parse_mode=(), link_preview=True,
            geo=None, period=60, contact=None, game=False, buttons=None
    ):
        """
        Creates a new inline result of photo type.

        Args:
            include_media (`bool`, optional):
                Whether the photo file used to display the result should be
                included in the message itself or not. By default, the photo
                is included, and the text parameter alters the caption.

            file (`obj`, optional):
                Same as ``file`` for `client.send_file()
                <telethon.client.uploads.UploadMethods.send_file>`.

        Example:
            .. code-block:: python

                results = [
                    # Sending just the photo when the user selects it.
                    builder.photo('/path/to/photo.jpg'),

                    # Including a caption with some in-memory photo.
                    photo_bytesio = ...
                    builder.photo(
                        photo_bytesio,
                        text='This will be the caption of the sent photo',
                    ),

                    # Sending just the message without including the photo.
                    builder.photo(
                        photo,
                        text='This will be a normal text message',
                        include_media=False,
                    ),
                ]
        """
        try:
            fh = utils.get_input_photo(file)
        except TypeError:
            _, media, _ = await self._client._file_to_media(
                file, allow_cache=True, as_image=True
            )
            if isinstance(media, types.InputPhoto):
                fh = media
            else:
                r = await self._client(functions.messages.UploadMediaRequest(
                    types.InputPeerSelf(), media=media
                ))
                fh = utils.get_input_photo(r.photo)

        result = types.InputBotInlineResultPhoto(
            id=id or '',
            type='photo',
            photo=fh,
            send_message=await self._message(
                text=text or '',
                parse_mode=parse_mode,
                link_preview=link_preview,
                media=include_media,
                geo=geo,
                period=period,
                contact=contact,
                game=game,
                buttons=buttons
            )
        )
        if id is None:
            result.id = hashlib.sha256(bytes(result)).hexdigest()

        return result

    # noinspection PyIncorrectDocstring
    async def document(
            self, file, title=None, *, description=None, type=None,
            mime_type=None, attributes=None, force_document=False,
            voice_note=False, video_note=False, use_cache=True, id=None,
            text=None, parse_mode=(), link_preview=True,
            geo=None, period=60, contact=None, game=False, buttons=None,
            include_media=True
    ):
        """
        Creates a new inline result of document type.

        `use_cache`, `mime_type`, `attributes`, `force_document`,
        `voice_note` and `video_note` are described in `client.send_file
        <telethon.client.uploads.UploadMethods.send_file>`.

        Args:
            file (`obj`):
                Same as ``file`` for `client.send_file()
                <telethon.client.uploads.UploadMethods.send_file>`.

            title (`str`, optional):
                The title to be shown for this result.

            description (`str`, optional):
                Further explanation of what this result means.

            type (`str`, optional):
                The type of the document. May be one of: article, audio,
                contact, file, geo, gif, photo, sticker, venue, video, voice.
                It will be automatically set if ``mime_type`` is specified,
                and default to ``'file'`` if no matching mime type is found.

            include_media (`bool`, optional):
                Whether the document file used to display the result should be
                included in the message itself or not. By default, the document
                is included, and the text parameter alters the caption.

        Example:
            .. code-block:: python

                results = [
                    # Sending just the file when the user selects it.
                    builder.document('/path/to/file.pdf'),

                    # Including a caption with some in-memory file.
                    file_bytesio = ...
                    builder.document(
                        file_bytesio,
                        text='This will be the caption of the sent file',
                    ),

                    # Sending just the message without including the file.
                    builder.document(
                        photo,
                        text='This will be a normal text message',
                        include_media=False,
                    ),
                ]
        """
        if type is None:
            if voice_note:
                type = 'voice'
            elif mime_type:
                for ty, mimes in _TYPE_TO_MIMES.items():
                    for mime in mimes:
                        if mime_type == mime:
                            type = ty
                            break

            if type is None:
                type = 'file'

        try:
            fh = utils.get_input_document(file)
        except TypeError:
            _, media, _ = await self._client._file_to_media(
                file,
                mime_type=mime_type,
                attributes=attributes,
                force_document=True,
                voice_note=voice_note,
                video_note=video_note,
                allow_cache=use_cache
            )
            if isinstance(media, types.InputDocument):
                fh = media
            else:
                r = await self._client(functions.messages.UploadMediaRequest(
                    types.InputPeerSelf(), media=media
                ))
                fh = utils.get_input_document(r.document)

        result = types.InputBotInlineResultDocument(
            id=id or '',
            type=type,
            document=fh,
            send_message=await self._message(
                # Empty string for text if there's media but text is None.
                # We may want to display a document but send text; however
                # default to sending the media (without text, i.e. stickers).
                text=text or '',
                parse_mode=parse_mode,
                link_preview=link_preview,
                media=include_media,
                geo=geo,
                period=period,
                contact=contact,
                game=game,
                buttons=buttons
            ),
            title=title,
            description=description
        )
        if id is None:
            result.id = hashlib.sha256(bytes(result)).hexdigest()

        return result

    # noinspection PyIncorrectDocstring
    async def game(
            self, short_name, *, id=None,
            text=None, parse_mode=(), link_preview=True,
            geo=None, period=60, contact=None, game=False, buttons=None
    ):
        """
        Creates a new inline result of game type.

        Args:
            short_name (`str`):
                The short name of the game to use.
        """
        result = types.InputBotInlineResultGame(
            id=id or '',
            short_name=short_name,
            send_message=await self._message(
                text=text, parse_mode=parse_mode, link_preview=link_preview,
                geo=geo, period=period,
                contact=contact,
                game=game,
                buttons=buttons
            )
        )
        if id is None:
            result.id = hashlib.sha256(bytes(result)).hexdigest()

        return result

    async def _message(
            self, *,
            text=None, parse_mode=(), link_preview=True, media=False,
            geo=None, period=60, contact=None, game=False, buttons=None
    ):
        # Empty strings are valid but false-y; if they're empty use dummy '\0'
        args = ('\0' if text == '' else text, geo, contact, game)
        if sum(1 for x in args if x is not None and x is not False) != 1:
            raise ValueError(
                'Must set exactly one of text, geo, contact or game (set {})'
                .format(', '.join(x[0] for x in zip(
                    'text geo contact game'.split(), args) if x[1]) or 'none')
            )

        markup = self._client.build_reply_markup(buttons, inline_only=True)
        if text is not None:
            text, msg_entities = await self._client._parse_message_text(
                text, parse_mode
            )
            if media:
                # "MediaAuto" means it will use whatever media the inline
                # result itself has (stickers, photos, or documents), while
                # respecting the user's text (caption) and formatting.
                return types.InputBotInlineMessageMediaAuto(
                    message=text,
                    entities=msg_entities,
                    reply_markup=markup
                )
            else:
                return types.InputBotInlineMessageText(
                    message=text,
                    no_webpage=not link_preview,
                    entities=msg_entities,
                    reply_markup=markup
                )
        elif isinstance(geo, (types.InputGeoPoint, types.GeoPoint)):
            return types.InputBotInlineMessageMediaGeo(
                geo_point=utils.get_input_geo(geo),
                period=period,
                reply_markup=markup
            )
        elif isinstance(geo, (types.InputMediaVenue, types.MessageMediaVenue)):
            if isinstance(geo, types.InputMediaVenue):
                geo_point = geo.geo_point
            else:
                geo_point = geo.geo

            return types.InputBotInlineMessageMediaVenue(
                geo_point=geo_point,
                title=geo.title,
                address=geo.address,
                provider=geo.provider,
                venue_id=geo.venue_id,
                venue_type=geo.venue_type,
                reply_markup=markup
            )
        elif isinstance(contact, (
                types.InputMediaContact, types.MessageMediaContact)):
            return types.InputBotInlineMessageMediaContact(
                phone_number=contact.phone_number,
                first_name=contact.first_name,
                last_name=contact.last_name,
                vcard=contact.vcard,
                reply_markup=markup
            )
        elif game:
            return types.InputBotInlineMessageGame(
                reply_markup=markup
            )
        else:
            raise ValueError('No text, game or valid geo or contact given')
