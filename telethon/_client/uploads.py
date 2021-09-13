import hashlib
import io
import itertools
import os
import pathlib
import re
import typing
from io import BytesIO

from .._crypto import AES

from .._misc import utils, helpers
from .. import hints, _tl
from ..types import _custom

try:
    import PIL
    import PIL.Image
except ImportError:
    PIL = None


if typing.TYPE_CHECKING:
    from .telegramclient import TelegramClient


class _CacheType:
    """Like functools.partial but pretends to be the wrapped class."""
    def __init__(self, cls):
        self._cls = cls

    def __call__(self, *args, **kwargs):
        return self._cls(*args, file_reference=b'', **kwargs)

    def __eq__(self, other):
        return self._cls == other


def _resize_photo_if_needed(
        file, is_image, width=1280, height=1280, background=(255, 255, 255)):

    # https://github.com/telegramdesktop/tdesktop/blob/12905f0dcb9d513378e7db11989455a1b764ef75/Telegram/SourceFiles/boxes/photo_crop_box.cpp#L254
    if (not is_image
            or PIL is None
            or (isinstance(file, io.IOBase) and not file.seekable())):
        return file

    if isinstance(file, bytes):
        file = io.BytesIO(file)

    before = file.tell() if isinstance(file, io.IOBase) else None

    try:
        # Don't use a `with` block for `image`, or `file` would be closed.
        # See https://github.com/LonamiWebs/Telethon/issues/1121 for more.
        image = PIL.Image.open(file)
        try:
            kwargs = {'exif': image.info['exif']}
        except KeyError:
            kwargs = {}

        if image.width <= width and image.height <= height:
            return file

        image.thumbnail((width, height), PIL.Image.ANTIALIAS)

        alpha_index = image.mode.find('A')
        if alpha_index == -1:
            # If the image mode doesn't have alpha
            # channel then don't bother masking it away.
            result = image
        else:
            # We could save the resized image with the original format, but
            # JPEG often compresses better -> smaller size -> faster upload
            # We need to mask away the alpha channel ([3]), since otherwise
            # IOError is raised when trying to save alpha channels in JPEG.
            result = PIL.Image.new('RGB', image.size, background)
            result.paste(image, mask=image.split()[alpha_index])

        buffer = io.BytesIO()
        result.save(buffer, 'JPEG', **kwargs)
        buffer.seek(0)
        return buffer

    except IOError:
        return file
    finally:
        if before is not None:
            file.seek(before, io.SEEK_SET)


async def send_file(
        self: 'TelegramClient',
        entity: 'hints.EntityLike',
        file: 'typing.Union[hints.FileLike, typing.Sequence[hints.FileLike]]',
        *,
        caption: typing.Union[str, typing.Sequence[str]] = None,
        force_document: bool = False,
        file_size: int = None,
        clear_draft: bool = False,
        progress_callback: 'hints.ProgressCallback' = None,
        reply_to: 'hints.MessageIDLike' = None,
        attributes: 'typing.Sequence[_tl.TypeDocumentAttribute]' = None,
        thumb: 'hints.FileLike' = None,
        allow_cache: bool = True,
        parse_mode: str = (),
        formatting_entities: typing.Optional[typing.List[_tl.TypeMessageEntity]] = None,
        voice_note: bool = False,
        video_note: bool = False,
        buttons: 'hints.MarkupLike' = None,
        silent: bool = None,
        background: bool = None,
        supports_streaming: bool = False,
        schedule: 'hints.DateLike' = None,
        comment_to: 'typing.Union[int, _tl.Message]' = None,
        ttl: int = None,
        **kwargs) -> '_tl.Message':
    # TODO Properly implement allow_cache to reuse the sha256 of the file
    # i.e. `None` was used
    if not file:
        raise TypeError('Cannot use {!r} as file'.format(file))

    if not caption:
        caption = ''

    entity = await self.get_input_entity(entity)
    if comment_to is not None:
        entity, reply_to = await _get_comment_data(self, entity, comment_to)
    else:
        reply_to = utils.get_message_id(reply_to)

    # First check if the user passed an iterable, in which case
    # we may want to send grouped.
    if utils.is_list_like(file):
        if utils.is_list_like(caption):
            captions = caption
        else:
            captions = [caption]

        result = []
        while file:
            result += await _send_album(
                self, entity, file[:10], caption=captions[:10],
                progress_callback=progress_callback, reply_to=reply_to,
                parse_mode=parse_mode, silent=silent, schedule=schedule,
                supports_streaming=supports_streaming, clear_draft=clear_draft,
                force_document=force_document, background=background,
            )
            file = file[10:]
            captions = captions[10:]

        for doc, cap in zip(file, captions):
            result.append(await self.send_file(
                entity, doc, allow_cache=allow_cache,
                caption=cap, force_document=force_document,
                progress_callback=progress_callback, reply_to=reply_to,
                attributes=attributes, thumb=thumb, voice_note=voice_note,
                video_note=video_note, buttons=buttons, silent=silent,
                supports_streaming=supports_streaming, schedule=schedule,
                clear_draft=clear_draft, background=background,
                **kwargs
            ))

        return result

    if formatting_entities is not None:
        msg_entities = formatting_entities
    else:
        caption, msg_entities =\
            await self._parse_message_text(caption, parse_mode)

    file_handle, media, image = await _file_to_media(
        self, file, force_document=force_document,
        file_size=file_size,
        progress_callback=progress_callback,
        attributes=attributes,  allow_cache=allow_cache, thumb=thumb,
        voice_note=voice_note, video_note=video_note,
        supports_streaming=supports_streaming, ttl=ttl
    )

    # e.g. invalid cast from :tl:`MessageMediaWebPage`
    if not media:
        raise TypeError('Cannot use {!r} as file'.format(file))

    markup = self.build_reply_markup(buttons)
    request = _tl.fn.messages.SendMedia(
        entity, media, reply_to_msg_id=reply_to, message=caption,
        entities=msg_entities, reply_markup=markup, silent=silent,
        schedule_date=schedule, clear_draft=clear_draft,
        background=background
    )
    return self._get_response_message(request, await self(request), entity)

async def _send_album(self: 'TelegramClient', entity, files, caption='',
                        progress_callback=None, reply_to=None,
                        parse_mode=(), silent=None, schedule=None,
                        supports_streaming=None, clear_draft=None,
                        force_document=False, background=None, ttl=None):
    """Specialized version of .send_file for albums"""
    # We don't care if the user wants to avoid cache, we will use it
    # anyway. Why? The cached version will be exactly the same thing
    # we need to produce right now to send albums (uploadMedia), and
    # cache only makes a difference for documents where the user may
    # want the attributes used on them to change.
    #
    # In theory documents can be sent inside the albums but they appear
    # as different messages (not inside the album), and the logic to set
    # the attributes/avoid cache is already written in .send_file().
    entity = await self.get_input_entity(entity)
    if not utils.is_list_like(caption):
        caption = (caption,)

    captions = []
    for c in reversed(caption):  # Pop from the end (so reverse)
        captions.append(await self._parse_message_text(c or '', parse_mode))

    reply_to = utils.get_message_id(reply_to)

    # Need to upload the media first, but only if they're not cached yet
    media = []
    for file in files:
        # Albums want :tl:`InputMedia` which, in theory, includes
        # :tl:`InputMediaUploadedPhoto`. However using that will
        # make it `raise MediaInvalidError`, so we need to upload
        # it as media and then convert that to :tl:`InputMediaPhoto`.
        fh, fm, _ = await _file_to_media(
            self, file, supports_streaming=supports_streaming,
            force_document=force_document, ttl=ttl)
        if isinstance(fm, (_tl.InputMediaUploadedPhoto, _tl.InputMediaPhotoExternal)):
            r = await self(_tl.fn.messages.UploadMedia(
                entity, media=fm
            ))

            fm = utils.get_input_media(r.photo)
        elif isinstance(fm, _tl.InputMediaUploadedDocument):
            r = await self(_tl.fn.messages.UploadMedia(
                entity, media=fm
            ))

            fm = utils.get_input_media(
                r.document, supports_streaming=supports_streaming)

        if captions:
            caption, msg_entities = captions.pop()
        else:
            caption, msg_entities = '', None
        media.append(_tl.InputSingleMedia(
            fm,
            message=caption,
            entities=msg_entities
            # random_id is autogenerated
        ))

    # Now we can construct the multi-media request
    request = _tl.fn.messages.SendMultiMedia(
        entity, reply_to_msg_id=reply_to, multi_media=media,
        silent=silent, schedule_date=schedule, clear_draft=clear_draft,
        background=background
    )
    result = await self(request)

    random_ids = [m.random_id for m in media]
    return self._get_response_message(random_ids, result, entity)

async def upload_file(
        self: 'TelegramClient',
        file: 'hints.FileLike',
        *,
        part_size_kb: float = None,
        file_size: int = None,
        file_name: str = None,
        use_cache: type = None,
        key: bytes = None,
        iv: bytes = None,
        progress_callback: 'hints.ProgressCallback' = None) -> '_tl.TypeInputFile':
    if isinstance(file, (_tl.InputFile, _tl.InputFileBig)):
        return file  # Already uploaded

    pos = 0
    async with helpers._FileStream(file, file_size=file_size) as stream:
        # Opening the stream will determine the correct file size
        file_size = stream.file_size

        if not part_size_kb:
            part_size_kb = utils.get_appropriated_part_size(file_size)

        if part_size_kb > 512:
            raise ValueError('The part size must be less or equal to 512KB')

        part_size = int(part_size_kb * 1024)
        if part_size % 1024 != 0:
            raise ValueError(
                'The part size must be evenly divisible by 1024')

        # Set a default file name if None was specified
        file_id = helpers.generate_random_long()
        if not file_name:
            file_name = stream.name or str(file_id)

        # If the file name lacks extension, add it if possible.
        # Else Telegram complains with `PHOTO_EXT_INVALID_ERROR`
        # even if the uploaded image is indeed a photo.
        if not os.path.splitext(file_name)[-1]:
            file_name += utils._get_extension(stream)

        # Determine whether the file is too big (over 10MB) or not
        # Telegram does make a distinction between smaller or larger files
        is_big = file_size > 10 * 1024 * 1024
        hash_md5 = hashlib.md5()

        part_count = (file_size + part_size - 1) // part_size
        self._log[__name__].info('Uploading file of %d bytes in %d chunks of %d',
                                file_size, part_count, part_size)

        pos = 0
        for part_index in range(part_count):
            # Read the file by in chunks of size part_size
            part = await helpers._maybe_await(stream.read(part_size))

            if not isinstance(part, bytes):
                raise TypeError(
                    'file descriptor returned {}, not bytes (you must '
                    'open the file in bytes mode)'.format(type(part)))

            # `file_size` could be wrong in which case `part` may not be
            # `part_size` before reaching the end.
            if len(part) != part_size and part_index < part_count - 1:
                raise ValueError(
                    'read less than {} before reaching the end; either '
                    '`file_size` or `read` are wrong'.format(part_size))

            pos += len(part)

            # Encryption part if needed
            if key and iv:
                part = AES.encrypt_ige(part, key, iv)

            if not is_big:
                # Bit odd that MD5 is only needed for small files and not
                # big ones with more chance for corruption, but that's
                # what Telegram wants.
                hash_md5.update(part)

            # The SavePart is different depending on whether
            # the file is too large or not (over or less than 10MB)
            if is_big:
                request = _tl.fn.upload.SaveBigFilePart(
                    file_id, part_index, part_count, part)
            else:
                request = _tl.fn.upload.SaveFilePart(
                    file_id, part_index, part)

            result = await self(request)
            if result:
                self._log[__name__].debug('Uploaded %d/%d',
                                            part_index + 1, part_count)
                if progress_callback:
                    await helpers._maybe_await(progress_callback(pos, file_size))
            else:
                raise RuntimeError(
                    'Failed to upload file part {}.'.format(part_index))

    if is_big:
        return _tl.InputFileBig(file_id, part_count, file_name)
    else:
        return _custom.InputSizedFile(
            file_id, part_count, file_name, md5=hash_md5, size=file_size
        )


async def _file_to_media(
        self, file, force_document=False, file_size=None,
        progress_callback=None, attributes=None, thumb=None,
        allow_cache=True, voice_note=False, video_note=False,
        supports_streaming=False, mime_type=None, as_image=None,
        ttl=None):
    if not file:
        return None, None, None

    if isinstance(file, pathlib.Path):
        file = str(file.absolute())

    is_image = utils.is_image(file)
    if as_image is None:
        as_image = is_image and not force_document

    # `aiofiles` do not base `io.IOBase` but do have `read`, so we
    # just check for the read attribute to see if it's file-like.
    if not isinstance(file, (str, bytes, _tl.InputFile, _tl.InputFileBig))\
            and not hasattr(file, 'read'):
        # The user may pass a Message containing media (or the media,
        # or anything similar) that should be treated as a file. Try
        # getting the input media for whatever they passed and send it.
        #
        # We pass all attributes since these will be used if the user
        # passed :tl:`InputFile`, and all information may be relevant.
        try:
            return (None, utils.get_input_media(
                file,
                is_photo=as_image,
                attributes=attributes,
                force_document=force_document,
                voice_note=voice_note,
                video_note=video_note,
                supports_streaming=supports_streaming,
                ttl=ttl
            ), as_image)
        except TypeError:
            # Can't turn whatever was given into media
            return None, None, as_image

    media = None
    file_handle = None

    if isinstance(file, (_tl.InputFile, _tl.InputFileBig)):
        file_handle = file
    elif not isinstance(file, str) or os.path.isfile(file):
        file_handle = await self.upload_file(
            _resize_photo_if_needed(file, as_image),
            file_size=file_size,
            progress_callback=progress_callback
        )
    elif re.match('https?://', file):
        if as_image:
            media = _tl.InputMediaPhotoExternal(file, ttl_seconds=ttl)
        else:
            media = _tl.InputMediaDocumentExternal(file, ttl_seconds=ttl)
    else:
        bot_file = utils.resolve_bot_file_id(file)
        if bot_file:
            media = utils.get_input_media(bot_file, ttl=ttl)

    if media:
        pass  # Already have media, don't check the rest
    elif not file_handle:
        raise ValueError(
            'Failed to convert {} to media. Not an existing file, '
            'an HTTP URL or a valid bot-API-like file ID'.format(file)
        )
    elif as_image:
        media = _tl.InputMediaUploadedPhoto(file_handle, ttl_seconds=ttl)
    else:
        attributes, mime_type = utils.get_attributes(
            file,
            mime_type=mime_type,
            attributes=attributes,
            force_document=force_document and not is_image,
            voice_note=voice_note,
            video_note=video_note,
            supports_streaming=supports_streaming,
            thumb=thumb
        )

        if not thumb:
            thumb = None
        else:
            if isinstance(thumb, pathlib.Path):
                thumb = str(thumb.absolute())
            thumb = await self.upload_file(thumb, file_size=file_size)

        media = _tl.InputMediaUploadedDocument(
            file=file_handle,
            mime_type=mime_type,
            attributes=attributes,
            thumb=thumb,
            force_file=force_document and not is_image,
            ttl_seconds=ttl
        )
    return file_handle, media, as_image
