import hashlib

from .. import functions, types
from ... import utils


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
            self, file, *, id=None,
            text=None, parse_mode=(), link_preview=True,
            geo=None, period=60, contact=None, game=False, buttons=None
    ):
        """
        Creates a new inline result of photo type.

        Args:
            file (`obj`, optional):
                Same as ``file`` for `client.send_file()
                <telethon.client.uploads.UploadMethods.send_file>`.
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
            geo=None, period=60, contact=None, game=False, buttons=None
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
                The type of the document. May be one of: photo, gif,
                mpeg4_gif, video, audio, voice, document, sticker.

                See "Type of the result" in https://core.telegram.org/bots/api.
        """
        if type is None:
            if voice_note:
                type = 'voice'
            else:
                type = 'document'

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
            text=None, parse_mode=(), link_preview=True,
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
            if not text:  # Automatic media on empty string, like stickers
                return types.InputBotInlineMessageMediaAuto('')

            text, msg_entities = await self._client._parse_message_text(
                text, parse_mode
            )
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
