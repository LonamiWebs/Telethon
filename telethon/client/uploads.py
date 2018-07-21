import hashlib
import io
import logging
import os
import pathlib
import re
from io import BytesIO
from mimetypes import guess_type

from .messageparse import MessageParseMethods
from .users import UserMethods
from .buttons import ButtonMethods
from .. import utils, helpers
from ..tl import types, functions, custom

__log__ = logging.getLogger(__name__)


class UploadMethods(ButtonMethods, MessageParseMethods, UserMethods):

    # region Public methods

    async def send_file(
            self, entity, file, *, caption='', force_document=False,
            progress_callback=None, reply_to=None, attributes=None,
            thumb=None, allow_cache=True, parse_mode=utils.Default,
            voice_note=False, video_note=False, buttons=None, silent=None,
            **kwargs):
        """
        Sends a file to the specified entity.

        Args:
            entity (`entity`):
                Who will receive the file.

            file (`str` | `bytes` | `file` | `media`):
                The path of the file, byte array, or stream that will be sent.
                Note that if a byte array or a stream is given, a filename
                or its type won't be inferred, and it will be sent as an
                "unnamed application/octet-stream".

                Furthermore the file may be any media (a message, document,
                photo or similar) so that it can be resent without the need
                to download and re-upload it again.

                If a list or similar is provided, the files in it will be
                sent as an album in the order in which they appear, sliced
                in chunks of 10 if more than 10 are given.

            caption (`str`, optional):
                Optional caption for the sent media message.

            force_document (`bool`, optional):
                If left to ``False`` and the file is a path that ends with
                the extension of an image file or a video file, it will be
                sent as such. Otherwise always as a document.

            progress_callback (`callable`, optional):
                A callback function accepting two parameters:
                ``(sent bytes, total)``.

            reply_to (`int` | :tl:`Message`):
                Same as `reply_to` from `send_message`.

            attributes (`list`, optional):
                Optional attributes that override the inferred ones, like
                :tl:`DocumentAttributeFilename` and so on.

            thumb (`str` | `bytes` | `file`, optional):
                Optional JPEG thumbnail (for documents). **Telegram will
                ignore this parameter** unless you pass a ``.jpg`` file!

            allow_cache (`bool`, optional):
                Whether to allow using the cached version stored in the
                database or not. Defaults to ``True`` to avoid re-uploads.
                Must be ``False`` if you wish to use different attributes
                or thumb than those that were used when the file was cached.

            parse_mode (`object`, optional):
                See the `TelegramClient.parse_mode` property for allowed
                values. Markdown parsing will be used by default.

            voice_note (`bool`, optional):
                If ``True`` the audio will be sent as a voice note.

                Set `allow_cache` to ``False`` if you sent the same file
                without this setting before for it to work.

            video_note (`bool`, optional):
                If ``True`` the video will be sent as a video note,
                also known as a round video message.

                Set `allow_cache` to ``False`` if you sent the same file
                without this setting before for it to work.

            buttons (`list`, `custom.Button <telethon.tl.custom.button.Button>`,
            :tl:`KeyboardButton`):
                The matrix (list of lists), row list or button to be shown
                after sending the message. This parameter will only work if
                you have signed in as a bot. You can also pass your own
                :tl:`ReplyMarkup` here.

            silent (`bool`, optional):
                Whether the message should notify people in a broadcast
                channel or not. Defaults to ``False``, which means it will
                notify them. Set it to ``True`` to alter this behaviour.

        Notes:
            If the ``hachoir3`` package (``hachoir`` module) is installed,
            it will be used to determine metadata from audio and video files.

        Returns:
            The `telethon.tl.custom.message.Message` (or messages) containing
            the sent file, or messages if a list of them was passed.
        """
        # First check if the user passed an iterable, in which case
        # we may want to send as an album if all are photo files.
        if utils.is_list_like(file):
            # TODO Fix progress_callback
            images = []
            if force_document:
                documents = file
            else:
                documents = []
                for x in file:
                    if utils.is_image(x):
                        images.append(x)
                    else:
                        documents.append(x)

            result = []
            while images:
                result += await self._send_album(
                    entity, images[:10], caption=caption,
                    progress_callback=progress_callback, reply_to=reply_to,
                    parse_mode=parse_mode, silent=silent
                )
                images = images[10:]

            for x in documents:
                result.append(await self.send_file(
                    entity, x, allow_cache=allow_cache,
                    caption=caption, force_document=force_document,
                    progress_callback=progress_callback, reply_to=reply_to,
                    attributes=attributes, thumb=thumb, voice_note=voice_note,
                    video_note=video_note, buttons=buttons, silent=silent,
                    **kwargs
                ))

            return result

        entity = await self.get_input_entity(entity)
        reply_to = utils.get_message_id(reply_to)

        # Not document since it's subject to change.
        # Needed when a Message is passed to send_message and it has media.
        if 'entities' in kwargs:
            msg_entities = kwargs['entities']
        else:
            caption, msg_entities =\
                await self._parse_message_text(caption, parse_mode)

        file_handle, media = await self._file_to_media(
            file, force_document=force_document,
            progress_callback=progress_callback,
            attributes=attributes,  allow_cache=allow_cache, thumb=thumb,
            voice_note=voice_note, video_note=video_note
        )

        markup = self.build_reply_markup(buttons)
        request = functions.messages.SendMediaRequest(
            entity, media, reply_to_msg_id=reply_to, message=caption,
            entities=msg_entities, reply_markup=markup, silent=silent
        )
        msg = self._get_response_message(request, await self(request), entity)
        self._cache_media(msg, file, file_handle, force_document=force_document)

        return msg

    async def _send_album(self, entity, files, caption='',
                    progress_callback=None, reply_to=None,
                    parse_mode=utils.Default, silent=None):
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
            # fh will either be InputPhoto or a modified InputFile
            fh = await self.upload_file(file, use_cache=types.InputPhoto)
            if not isinstance(fh, types.InputPhoto):
                r = await self(functions.messages.UploadMediaRequest(
                    entity, media=types.InputMediaUploadedPhoto(fh)
                ))
                input_photo = utils.get_input_photo(r.photo)
                self.session.cache_file(fh.md5, fh.size, input_photo)
                fh = input_photo

            if captions:
                caption, msg_entities = captions.pop()
            else:
                caption, msg_entities = '', None
            media.append(types.InputSingleMedia(
                types.InputMediaPhoto(fh),
                message=caption,
                entities=msg_entities
            ))

        # Now we can construct the multi-media request
        result = await self(functions.messages.SendMultiMediaRequest(
            entity, reply_to_msg_id=reply_to, multi_media=media, silent=silent
        ))
        return [
            self._get_response_message(update.id, result, entity)
            for update in result.updates
            if isinstance(update, types.UpdateMessageID)
        ]

    async def upload_file(
            self, file, *, part_size_kb=None, file_name=None, use_cache=None,
            progress_callback=None):
        """
        Uploads the specified file and returns a handle (an instance of
        :tl:`InputFile` or :tl:`InputFileBig`, as required) which can be
        later used before it expires (they are usable during less than a day).

        Uploading a file will simply return a "handle" to the file stored
        remotely in the Telegram servers, which can be later used on. This
        will **not** upload the file to your own chat or any chat at all.

        Args:
            file (`str` | `bytes` | `file`):
                The path of the file, byte array, or stream that will be sent.
                Note that if a byte array or a stream is given, a filename
                or its type won't be inferred, and it will be sent as an
                "unnamed application/octet-stream".

            part_size_kb (`int`, optional):
                Chunk size when uploading files. The larger, the less
                requests will be made (up to 512KB maximum).

            file_name (`str`, optional):
                The file name which will be used on the resulting InputFile.
                If not specified, the name will be taken from the ``file``
                and if this is not a ``str``, it will be ``"unnamed"``.

            use_cache (`type`, optional):
                The type of cache to use (currently either :tl:`InputDocument`
                or :tl:`InputPhoto`). If present and the file is small enough
                to need the MD5, it will be checked against the database,
                and if a match is found, the upload won't be made. Instead,
                an instance of type ``use_cache`` will be returned.

            progress_callback (`callable`, optional):
                A callback function accepting two parameters:
                ``(sent bytes, total)``.

        Returns:
            :tl:`InputFileBig` if the file size is larger than 10MB,
            `telethon.tl.custom.input_sized_file.InputSizedFile`
            (subclass of :tl:`InputFile`) otherwise.
        """
        if isinstance(file, (types.InputFile, types.InputFileBig)):
            return file  # Already uploaded

        if not file_name and getattr(file, 'name', None):
            file_name = file.name

        if isinstance(file, str):
            file_size = os.path.getsize(file)
        elif isinstance(file, bytes):
            file_size = len(file)
        else:
            file = file.read()
            file_size = len(file)

        # File will now either be a string or bytes
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
            if isinstance(file, str):
                file_name = os.path.basename(file)
            else:
                file_name = str(file_id)

        # Determine whether the file is too big (over 10MB) or not
        # Telegram does make a distinction between smaller or larger files
        is_large = file_size > 10 * 1024 * 1024
        hash_md5 = hashlib.md5()
        if not is_large:
            # Calculate the MD5 hash before anything else.
            # As this needs to be done always for small files,
            # might as well do it before anything else and
            # check the cache.
            if isinstance(file, str):
                with open(file, 'rb') as stream:
                    file = stream.read()
            hash_md5.update(file)
            if use_cache:
                cached = self.session.get_file(
                    hash_md5.digest(), file_size, cls=use_cache
                )
                if cached:
                    return cached

        part_count = (file_size + part_size - 1) // part_size
        __log__.info('Uploading file of %d bytes in %d chunks of %d',
                     file_size, part_count, part_size)

        with open(file, 'rb') if isinstance(file, str) else BytesIO(file)\
                as stream:
            for part_index in range(part_count):
                # Read the file by in chunks of size part_size
                part = stream.read(part_size)

                # The SavePartRequest is different depending on whether
                # the file is too large or not (over or less than 10MB)
                if is_large:
                    request = functions.upload.SaveBigFilePartRequest(
                        file_id, part_index, part_count, part)
                else:
                    request = functions.upload.SaveFilePartRequest(
                        file_id, part_index, part)

                result = await self(request)
                if result:
                    __log__.debug('Uploaded %d/%d', part_index + 1,
                                  part_count)
                    if progress_callback:
                        progress_callback(stream.tell(), file_size)
                else:
                    raise RuntimeError(
                        'Failed to upload file part {}.'.format(part_index))

        if is_large:
            return types.InputFileBig(file_id, part_count, file_name)
        else:
            return custom.InputSizedFile(
                file_id, part_count, file_name, md5=hash_md5, size=file_size
            )

    # endregion

    async def _file_to_media(
            self, file, force_document=False,
            progress_callback=None, attributes=None, thumb=None,
            allow_cache=True, voice_note=False, video_note=False):
        if not file:
            return None, None

        if isinstance(file, pathlib.Path):
            file = str(file.absolute())

        if not isinstance(file, (str, bytes, io.IOBase)):
            # The user may pass a Message containing media (or the media,
            # or anything similar) that should be treated as a file. Try
            # getting the input media for whatever they passed and send it.
            try:
                return None, utils.get_input_media(file)
            except TypeError:
                return None, None  # Can't turn whatever was given into media

        media = None
        as_image = utils.is_image(file) and not force_document
        use_cache = types.InputPhoto if as_image else types.InputDocument
        if isinstance(file, str) and re.match('https?://', file):
            file_handle = None
            if as_image:
                media = types.InputMediaPhotoExternal(file)
            elif not force_document and utils.is_gif(file):
                media = types.InputMediaGifExternal(file, '')
            else:
                media = types.InputMediaDocumentExternal(file)
        else:
            file_handle = await self.upload_file(
                file, progress_callback=progress_callback,
                use_cache=use_cache if allow_cache else None
            )

        if media:
            pass  # Already have media, don't check the rest
        elif isinstance(file_handle, use_cache):
            # File was cached, so an instance of use_cache was returned
            if as_image:
                media = types.InputMediaPhoto(file_handle)
            else:
                media = types.InputMediaDocument(file_handle)
        elif as_image:
            media = types.InputMediaUploadedPhoto(file_handle)
        else:
            attributes, mime_type = utils.get_attributes(
                file,
                attributes=attributes,
                force_document=force_document,
                voice_note=voice_note,
                video_note=video_note
            )

            input_kw = {}
            if thumb:
                input_kw['thumb'] = await self.upload_file(thumb)

            media = types.InputMediaUploadedDocument(
                file=file_handle,
                mime_type=mime_type,
                attributes=attributes,
                **input_kw
            )
        return file_handle, media

    def _cache_media(self, msg, file, file_handle,
                     force_document=False):
        if file and msg and isinstance(file_handle,
                                       custom.InputSizedFile):
            # There was a response message and we didn't use cached
            # version, so cache whatever we just sent to the database.
            md5, size = file_handle.md5, file_handle.size
            if utils.is_image(file) and not force_document:
                to_cache = utils.get_input_photo(msg.media.photo)
            else:
                to_cache = utils.get_input_document(msg.media.document)
            self.session.cache_file(md5, size, to_cache)

    # endregion
