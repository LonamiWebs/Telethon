import hashlib
import io
import itertools
import os
import pathlib
import re
import typing
from io import BytesIO

from .._crypto import AES

from .._misc import utils, helpers, hints
from ..types import _custom
from .. import _tl

try:
    import PIL
    import PIL.Image
except ImportError:
    PIL = None


if typing.TYPE_CHECKING:
    from .telegramclient import TelegramClient


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
        dialog: 'hints.DialogLike',
        file: typing.Optional[hints.FileLike] = None,
        *,
        # - Message contents
        # Formatting
        caption: 'hints.MessageLike' = '',
        markdown: str = None,
        html: str = None,
        formatting_entities: list = None,
        link_preview: bool = (),
        # Media
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
        # - Send options
        reply_to: 'typing.Union[int, _tl.Message]' = None,
        clear_draft: bool = False,
        background: bool = None,
        noforwards: bool = None,
        send_as: 'hints.DialogLike' = None,
        schedule: 'hints.DateLike' = None,
        comment_to: 'typing.Union[int, _tl.Message]' = None,
) -> '_tl.Message':
    self.send_message(
        dialog=dialog,
        message=caption,
        markdown=markdown,
        html=html,
        formatting_entities=formatting_entities,
        link_preview=link_preview,
        file=file,
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
        reply_to=reply_to,
        clear_draft=clear_draft,
        background=background,
        schedule=schedule,
        comment_to=comment_to,
        noforwards=noforwards,
        send_as=send_as
    )

async def _send_album(self: 'TelegramClient', entity, files, caption='',
                        progress_callback=None, reply_to=None,
                        parse_mode=(), silent=None, schedule=None,
                        supports_streaming=None, clear_draft=None,
                        force_document=False, background=None, ttl=None,
                        send_as=None, noforwards=None):
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
    entity = await self._get_input_peer(entity)
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
        background=background, noforwards=noforwards, send_as=send_as
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
    """
    Uploads a file to Telegram's servers, without sending it.

    .. note::

        Generally, you want to use `send_file` instead.

    This method returns a handle (an instance of :tl:`InputFile` or
    :tl:`InputFileBig`, as required) which can be later used before
    it expires (they are usable during less than a day).

    Uploading a file will simply return a "handle" to the file stored
    remotely in the Telegram servers, which can be later used on. This
    will **not** upload the file to your own chat or any chat at all.

    Arguments
        file (`str` | `bytes` | `file`):
            The path of the file, byte array, or stream that will be sent.
            Note that if a byte array or a stream is given, a filename
            or its type won't be inferred, and it will be sent as an
            "unnamed application/octet-stream".

        part_size_kb (`int`, optional):
            Chunk size when uploading files. The larger, the less
            requests will be made (up to 512KB maximum).

        file_size (`int`, optional):
            The size of the file to be uploaded, which will be determined
            automatically if not specified.

            If the file size can't be determined beforehand, the entire
            file will be read in-memory to find out how large it is.

        file_name (`str`, optional):
            The file name which will be used on the resulting InputFile.
            If not specified, the name will be taken from the ``file``
            and if this is not a `str`, it will be ``"unnamed"``.

        use_cache (`type`, optional):
            This parameter currently does nothing, but is kept for
            backward-compatibility (and it may get its use back in
            the future).

        key ('bytes', optional):
            In case of an encrypted upload (secret chats) a key is supplied

        iv ('bytes', optional):
            In case of an encrypted upload (secret chats) an iv is supplied

        progress_callback (`callable`, optional):
            A callback function accepting two parameters:
            ``(sent bytes, total)``.

    Returns
        :tl:`InputFileBig` if the file size is larger than 10MB,
        `InputSizedFile <telethon.tl._custom.inputsizedfile.InputSizedFile>`
        (subclass of :tl:`InputFile`) otherwise.

    Example
        .. code-block:: python

            # Photos as photo and document
            file = await client.upload_file('photo.jpg')
            await client.send_file(chat, file)                       # sends as photo
            await client.send_file(chat, file, force_document=True)  # sends as document

            file.name = 'not a photo.jpg'
            await client.send_file(chat, file, force_document=True)  # document, new name

            # As song or as voice note
            file = await client.upload_file('song.ogg')
            await client.send_file(chat, file)                   # sends as song
            await client.send_file(chat, file, voice_note=True)  # sends as voice note
    """
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


