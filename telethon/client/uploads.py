import hashlib
import io
import itertools
import os
import pathlib
import re
import typing
from io import BytesIO

from ..crypto import AES

from .. import utils, helpers, hints
from ..tl import types, functions, custom

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
        file, is_image, width=2560, height=2560, background=(255, 255, 255)):

    # https://github.com/telegramdesktop/tdesktop/blob/12905f0dcb9d513378e7db11989455a1b764ef75/Telegram/SourceFiles/boxes/photo_crop_box.cpp#L254
    if (not is_image
            or PIL is None
            or (isinstance(file, io.IOBase) and not file.seekable())):
        return file

    if isinstance(file, bytes):
        file = io.BytesIO(file)

    if isinstance(file, io.IOBase):
        # Pillow seeks to 0 unconditionally later anyway
        old_pos = file.tell()
        file.seek(0, io.SEEK_END)
        before = file.tell()
    elif isinstance(file, str) and os.path.exists(file):
        # Check if file exists as a path and if so, get its size on disk
        before = os.path.getsize(file)
    else:
        # Would be weird...
        before = None

    try:
        # Don't use a `with` block for `image`, or `file` would be closed.
        # See https://github.com/LonamiWebs/Telethon/issues/1121 for more.
        image = PIL.Image.open(file)
        try:
            kwargs = {'exif': image.info['exif']}
        except KeyError:
            kwargs = {}

        if image.mode == 'RGB':
            # Check if image is within acceptable bounds, if so, check if the image is at or below 10 MB, or assume it isn't if size is None or 0
            if image.width <= width and image.height <= height and (before <= 10000000 if before else False):
                return file

            # If the image is already RGB, don't convert it
            # certain modes such as 'P' have no alpha index but can't be saved as JPEG directly
            image.thumbnail((width, height), PIL.Image.LANCZOS)
            result = image
        else:
            # We could save the resized image with the original format, but
            # JPEG often compresses better -> smaller size -> faster upload
            # We need to mask away the alpha channel ([3]), since otherwise
            # IOError is raised when trying to save alpha channels in JPEG.
            image.thumbnail((width, height), PIL.Image.LANCZOS)
            result = PIL.Image.new('RGB', image.size, background)
            mask = None

            if image.has_transparency_data:
                if image.mode == 'RGBA':
                    mask = image.getchannel('A')
                else:
                    mask = image.convert('RGBA').getchannel('A')

            result.paste(image, mask=mask)

        buffer = io.BytesIO()
        result.save(buffer, 'JPEG', progressive=True, **kwargs)
        buffer.seek(0)
        buffer.name = 'a.jpg'
        return buffer
    except IOError:
        return file
    finally:
        # The original position might matter
        if isinstance(file, io.IOBase):
            file.seek(old_pos)


class UploadMethods:

    # region Public methods

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
            attributes: 'typing.Sequence[types.TypeDocumentAttribute]' = None,
            thumb: 'hints.FileLike' = None,
            allow_cache: bool = True,
            parse_mode: str = (),
            formatting_entities: typing.Optional[
                typing.Union[
                    typing.List[types.TypeMessageEntity], typing.List[typing.List[types.TypeMessageEntity]]
                ]
            ] = None,
            voice_note: bool = False,
            video_note: bool = False,
            buttons: typing.Optional['hints.MarkupLike'] = None,
            silent: bool = None,
            background: bool = None,
            supports_streaming: bool = False,
            schedule: 'hints.DateLike' = None,
            comment_to: 'typing.Union[int, types.Message]' = None,
            ttl: int = None,
            nosound_video: bool = None,
            **kwargs) -> typing.Union[typing.List[typing.Any], typing.Any]:
        """
        Sends message with the given file to the specified entity.

        .. note::

            If the ``hachoir3`` package (``hachoir`` module) is installed,
            it will be used to determine metadata from audio and video files.

            If the ``pillow`` package is installed and you are sending a photo,
            it will be resized to fit within the maximum dimensions allowed
            by Telegram to avoid ``errors.PhotoInvalidDimensionsError``. This
            cannot be done if you are sending :tl:`InputFile`, however.

        Arguments
            entity (`entity`):
                Who will receive the file.

            file (`str` | `bytes` | `file` | `media`):
                The file to send, which can be one of:

                * A local file path to an in-disk file. The file name
                  will be the path's base name.

                * A `bytes` byte array with the file's data to send
                  (for example, by using ``text.encode('utf-8')``).
                  A default file name will be used.

                * A bytes `io.IOBase` stream over the file to send
                  (for example, by using ``open(file, 'rb')``).
                  Its ``.name`` property will be used for the file name,
                  or a default if it doesn't have one.

                * An external URL to a file over the internet. This will
                  send the file as "external" media, and Telegram is the
                  one that will fetch the media and send it.

                * A Bot API-like ``file_id``. You can convert previously
                  sent media to file IDs for later reusing with
                  `telethon.utils.pack_bot_file_id`.

                * A handle to an existing file (for example, if you sent a
                  message with media before, you can use its ``message.media``
                  as a file here).

                * A handle to an uploaded file (from `upload_file`).

                * A :tl:`InputMedia` instance. For example, if you want to
                  send a dice use :tl:`InputMediaDice`, or if you want to
                  send a contact use :tl:`InputMediaContact`.

                To send an album, you should provide a list in this parameter.

                If a list or similar is provided, the files in it will be
                sent as an album in the order in which they appear, sliced
                in chunks of 10 if more than 10 are given.

            caption (`str`, optional):
                Optional caption for the sent media message. When sending an
                album, the caption may be a list of strings, which will be
                assigned to the files pairwise.

            force_document (`bool`, optional):
                If left to `False` and the file is a path that ends with
                the extension of an image file or a video file, it will be
                sent as such. Otherwise always as a document.

            file_size (`int`, optional):
                The size of the file to be uploaded if it needs to be uploaded,
                which will be determined automatically if not specified.

                If the file size can't be determined beforehand, the entire
                file will be read in-memory to find out how large it is.

            clear_draft (`bool`, optional):
                Whether the existing draft should be cleared or not.

            progress_callback (`callable`, optional):
                A callback function accepting two parameters:
                ``(sent bytes, total)``.

            reply_to (`int` | `Message <telethon.tl.custom.message.Message>`):
                Same as `reply_to` from `send_message`.

            attributes (`list`, optional):
                Optional attributes that override the inferred ones, like
                :tl:`DocumentAttributeFilename` and so on.

            thumb (`str` | `bytes` | `file`, optional):
                Optional JPEG thumbnail (for documents). **Telegram will
                ignore this parameter** unless you pass a ``.jpg`` file!

                The file must also be small in dimensions and in disk size.
                Successful thumbnails were files below 20kB and 320x320px.
                Width/height and dimensions/size ratios may be important.
                For Telegram to accept a thumbnail, you must provide the
                dimensions of the underlying media through ``attributes=``
                with :tl:`DocumentAttributesVideo` or by installing the
                optional ``hachoir`` dependency.


            allow_cache (`bool`, optional):
                This parameter currently does nothing, but is kept for
                backward-compatibility (and it may get its use back in
                the future).

            parse_mode (`object`, optional):
                See the `TelegramClient.parse_mode
                <telethon.client.messageparse.MessageParseMethods.parse_mode>`
                property for allowed values. Markdown parsing will be used by
                default.

            formatting_entities (`list`, optional):
                Optional formatting entities for the sent media message. When sending an album,
                `formatting_entities` can be a list of lists, where each inner list contains
                `types.TypeMessageEntity`. Each inner list will be assigned to the corresponding
                file in a pairwise manner with the caption. If provided, the ``parse_mode``
                parameter will be ignored.

            voice_note (`bool`, optional):
                If `True` the audio will be sent as a voice note.

            video_note (`bool`, optional):
                If `True` the video will be sent as a video note,
                also known as a round video message.

            buttons (`list`, `custom.Button <telethon.tl.custom.button.Button>`, :tl:`KeyboardButton`):
                The matrix (list of lists), row list or button to be shown
                after sending the message. This parameter will only work if
                you have signed in as a bot. You can also pass your own
                :tl:`ReplyMarkup` here.

            silent (`bool`, optional):
                Whether the message should notify people with sound or not.
                Defaults to `False` (send with a notification sound unless
                the person has the chat muted). Set it to `True` to alter
                this behaviour.

            background (`bool`, optional):
                Whether the message should be send in background.

            supports_streaming (`bool`, optional):
                Whether the sent video supports streaming or not. Note that
                Telegram only recognizes as streamable some formats like MP4,
                and others like AVI or MKV will not work. You should convert
                these to MP4 before sending if you want them to be streamable.
                Unsupported formats will result in ``VideoContentTypeError``.

            schedule (`hints.DateLike`, optional):
                If set, the file won't send immediately, and instead
                it will be scheduled to be automatically sent at a later
                time.

            comment_to (`int` | `Message <telethon.tl.custom.message.Message>`, optional):
                Similar to ``reply_to``, but replies in the linked group of a
                broadcast channel instead (effectively leaving a "comment to"
                the specified message).

                This parameter takes precedence over ``reply_to``. If there is
                no linked chat, `telethon.errors.sgIdInvalidError` is raised.

            ttl (`int`. optional):
                The Time-To-Live of the file (also known as "self-destruct timer"
                or "self-destructing media"). If set, files can only be viewed for
                a short period of time before they disappear from the message
                history automatically.

                The value must be at least 1 second, and at most 60 seconds,
                otherwise Telegram will ignore this parameter.

                Not all types of media can be used with this parameter, such
                as text documents, which will fail with ``TtlMediaInvalidError``.

            nosound_video (`bool`, optional):
                Only applicable when sending a video file without an audio
                track. If set to ``True``, the video will be displayed in
                Telegram as a video. If set to ``False``, Telegram will attempt
                to display the video as an animated gif. (It may still display
                as a video due to other factors.) The value is ignored if set
                on non-video files. This is set to ``True`` for albums, as gifs
                cannot be sent in albums.

        Returns
            The `Message <telethon.tl.custom.message.Message>` (or messages)
            containing the sent file, or messages if a list of them was passed.

        Example
            .. code-block:: python

                # Normal files like photos
                await client.send_file(chat, '/my/photos/me.jpg', caption="It's me!")
                # or
                await client.send_message(chat, "It's me!", file='/my/photos/me.jpg')

                # Voice notes or round videos
                await client.send_file(chat, '/my/songs/song.mp3', voice_note=True)
                await client.send_file(chat, '/my/videos/video.mp4', video_note=True)

                # Custom thumbnails
                await client.send_file(chat, '/my/documents/doc.txt', thumb='photo.jpg')

                # Only documents
                await client.send_file(chat, '/my/photos/photo.png', force_document=True)

                # Albums
                await client.send_file(chat, [
                    '/my/photos/holiday1.jpg',
                    '/my/photos/holiday2.jpg',
                    '/my/drawings/portrait.png'
                ])

                # Printing upload progress
                def callback(current, total):
                    print('Uploaded', current, 'out of', total,
                          'bytes: {:.2%}'.format(current / total))

                await client.send_file(chat, file, progress_callback=callback)

                # Dices, including dart and other future emoji
                from telethon.tl import types
                await client.send_file(chat, types.InputMediaDice(''))
                await client.send_file(chat, types.InputMediaDice('🎯'))

                # Contacts
                await client.send_file(chat, types.InputMediaContact(
                    phone_number='+34 123 456 789',
                    first_name='Example',
                    last_name='',
                    vcard=''
                ))
        """
        # TODO Properly implement allow_cache to reuse the sha256 of the file
        # i.e. `None` was used
        if not file:
            raise TypeError('Cannot use {!r} as file'.format(file))

        if not caption:
            caption = ''

        if not formatting_entities:
            formatting_entities = []

        entity = await self.get_input_entity(entity)
        if comment_to is not None:
            entity, reply_to = await self._get_comment_data(entity, comment_to)
        else:
            reply_to = utils.get_message_id(reply_to)

        # First check if the user passed an iterable, in which case
        # we may want to send grouped.
        if utils.is_list_like(file):
            sent_count = 0
            used_callback = None if not progress_callback else (
                lambda s, t: progress_callback(sent_count + s, len(file))
            )

            if utils.is_list_like(caption):
                captions = caption
            else:
                captions = [caption]

            # Check that formatting_entities list is valid
            if all(utils.is_list_like(obj) for obj in formatting_entities):
                formatting_entities = formatting_entities
            elif utils.is_list_like(formatting_entities):
                formatting_entities = [formatting_entities]
            else:
                raise TypeError('The formatting_entities argument must be a list or a sequence of lists')

            # Check that all entities in all lists are of the correct type
            if not all(isinstance(ent, types.TypeMessageEntity) for sublist in formatting_entities for ent in sublist):
                raise TypeError('All entities must be instances of <types.TypeMessageEntity>')

            result = []
            while file:
                result += await self._send_album(
                    entity, file[:10], caption=captions[:10], formatting_entities=formatting_entities[:10],
                    progress_callback=used_callback, reply_to=reply_to,
                    parse_mode=parse_mode, silent=silent, schedule=schedule,
                    supports_streaming=supports_streaming, clear_draft=clear_draft,
                    force_document=force_document, background=background,
                )
                file = file[10:]
                captions = captions[10:]
                formatting_entities = formatting_entities[10:]
                sent_count += 10

            return result

        if formatting_entities:
            msg_entities = formatting_entities
        else:
            caption, msg_entities =\
                await self._parse_message_text(caption, parse_mode)

        file_handle, media, image = await self._file_to_media(
            file, force_document=force_document,
            file_size=file_size,
            progress_callback=progress_callback,
            attributes=attributes, allow_cache=allow_cache, thumb=thumb,
            voice_note=voice_note, video_note=video_note,
            supports_streaming=supports_streaming, ttl=ttl,
            nosound_video=nosound_video,
        )

        # e.g. invalid cast from :tl:`MessageMediaWebPage`
        if not media:
            raise TypeError('Cannot use {!r} as file'.format(file))

        markup = self.build_reply_markup(buttons)
        reply_to = None if reply_to is None else types.InputReplyToMessage(reply_to)
        request = functions.messages.SendMediaRequest(
            entity, media, reply_to=reply_to, message=caption,
            entities=msg_entities, reply_markup=markup, silent=silent,
            schedule_date=schedule, clear_draft=clear_draft,
            background=background
        )
        return self._get_response_message(request, await self(request), entity)

    async def _send_album(self: 'TelegramClient', entity, files, caption='',
                          formatting_entities=None,
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
        # In theory documents can be sent inside the albums, but they appear
        # as different messages (not inside the album), and the logic to set
        # the attributes/avoid cache is already written in .send_file().
        entity = await self.get_input_entity(entity)
        if not utils.is_list_like(caption):
            caption = (caption,)
        if not all(isinstance(obj, list) for obj in formatting_entities):
            formatting_entities = (formatting_entities,)

        captions = []
        # If the formatting_entities argument is provided, we don't use parse_mode
        if formatting_entities:
            # Pop from the end (so reverse)
            capt_with_ent = itertools.zip_longest(reversed(caption), reversed(formatting_entities), fillvalue=None)
            for msg_caption, msg_entities in capt_with_ent:
                captions.append((msg_caption, msg_entities))
        else:
            for c in reversed(caption):  # Pop from the end (so reverse)
                captions.append(await self._parse_message_text(c or '', parse_mode))

        reply_to = utils.get_message_id(reply_to)

        used_callback = None if not progress_callback else (
            # use an integer when sent matches total, to easily determine a file has been fully sent
            lambda s, t: progress_callback(sent_count + 1 if s == t else sent_count + s / t, len(files))
        )

        # Need to upload the media first, but only if they're not cached yet
        media = []
        for sent_count, file in enumerate(files):
            # Albums want :tl:`InputMedia` which, in theory, includes
            # :tl:`InputMediaUploadedPhoto`. However, using that will
            # make it `raise MediaInvalidError`, so we need to upload
            # it as media and then convert that to :tl:`InputMediaPhoto`.
            fh, fm, _ = await self._file_to_media(
                file, supports_streaming=supports_streaming,
                force_document=force_document, ttl=ttl,
                progress_callback=used_callback, nosound_video=True)
            if isinstance(fm, (types.InputMediaUploadedPhoto, types.InputMediaPhotoExternal)):
                r = await self(functions.messages.UploadMediaRequest(
                    entity, media=fm
                ))

                fm = utils.get_input_media(r.photo)
            elif isinstance(fm, (types.InputMediaUploadedDocument, types.InputMediaDocumentExternal)):
                r = await self(functions.messages.UploadMediaRequest(
                    entity, media=fm
                ))

                fm = utils.get_input_media(
                    r.document, supports_streaming=supports_streaming)

            if captions:
                caption, msg_entities = captions.pop()
            else:
                caption, msg_entities = '', None
            media.append(types.InputSingleMedia(
                fm,
                message=caption,
                entities=msg_entities
                # random_id is autogenerated
            ))

        # Now we can construct the multi-media request
        request = functions.messages.SendMultiMediaRequest(
            entity, reply_to=None if reply_to is None else types.InputReplyToMessage(reply_to), multi_media=media,
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
            progress_callback: 'hints.ProgressCallback' = None) -> 'types.TypeInputFile':
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

                When sending an album, the callback will receive a number
                between 0 and the amount of files as the "sent" parameter,
                and the amount of files as the "total". Note that the first
                parameter will be a floating point number to indicate progress
                within a file (e.g. ``2.5`` means it has sent 50% of the third
                file, because it's between 2 and 3).

        Returns
            :tl:`InputFileBig` if the file size is larger than 10MB,
            `InputSizedFile <telethon.tl.custom.inputsizedfile.InputSizedFile>`
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
        if isinstance(file, (types.InputFile, types.InputFileBig)):
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

                # The SavePartRequest is different depending on whether
                # the file is too large or not (over or less than 10MB)
                if is_big:
                    request = functions.upload.SaveBigFilePartRequest(
                        file_id, part_index, part_count, part)
                else:
                    request = functions.upload.SaveFilePartRequest(
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
            return types.InputFileBig(file_id, part_count, file_name)
        else:
            return custom.InputSizedFile(
                file_id, part_count, file_name, md5=hash_md5, size=file_size
            )

    # endregion

    async def _file_to_media(
            self, file, force_document=False, file_size=None,
            progress_callback=None, attributes=None, thumb=None,
            allow_cache=True, voice_note=False, video_note=False,
            supports_streaming=False, mime_type=None, as_image=None,
            ttl=None, nosound_video=None):
        if not file:
            return None, None, None

        if isinstance(file, pathlib.Path):
            file = str(file.absolute())

        is_image = utils.is_image(file)
        if as_image is None:
            as_image = is_image and not force_document

        # `aiofiles` do not base `io.IOBase` but do have `read`, so we
        # just check for the read attribute to see if it's file-like.
        if not isinstance(file, (str, bytes, types.InputFile, types.InputFileBig)) \
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

        if isinstance(file, (types.InputFile, types.InputFileBig)):
            file_handle = file
        elif not isinstance(file, str) or os.path.isfile(file):
            file_handle = await self.upload_file(
                _resize_photo_if_needed(file, as_image),
                file_size=file_size,
                progress_callback=progress_callback
            )
        elif re.match('https?://', file):
            if as_image:
                media = types.InputMediaPhotoExternal(file, ttl_seconds=ttl)
            else:
                media = types.InputMediaDocumentExternal(file, ttl_seconds=ttl)
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
            media = types.InputMediaUploadedPhoto(file_handle, ttl_seconds=ttl)
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

            # setting `nosound_video` to `True` doesn't affect videos with sound
            # instead it prevents sending silent videos as GIFs
            nosound_video = nosound_video if mime_type.split("/")[0] == 'video' else None

            media = types.InputMediaUploadedDocument(
                file=file_handle,
                mime_type=mime_type,
                attributes=attributes,
                thumb=thumb,
                force_file=force_document and not is_image,
                ttl_seconds=ttl,
                nosound_video=nosound_video
            )
        return file_handle, media, as_image

    # endregion
