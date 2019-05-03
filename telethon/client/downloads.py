import datetime
import io
import os
import pathlib
import typing

from .users import UserMethods
from .. import utils, helpers, errors, hints
from ..tl import TLObject, types, functions

try:
    import aiohttp
except ImportError:
    aiohttp = None

if typing.TYPE_CHECKING:
    from .telegramclient import TelegramClient


class DownloadMethods(UserMethods):

    # region Public methods

    async def download_profile_photo(
            self: 'TelegramClient',
            entity: hints.EntityLike,
            file: hints.FileLike = None,
            *,
            download_big: bool = True) -> typing.Optional[str]:
        """
        Downloads the profile photo of the given entity (user/chat/channel).

        Args:
            entity (`entity`):
                From who the photo will be downloaded.

                .. note::

                    This method expects the full entity (which has the data
                    to download the photo), not an input variant.

                    It's possible that sometimes you can't fetch the entity
                    from its input (since you can get errors like
                    ``ChannelPrivateError``) but you already have it through
                    another call, like getting a forwarded message from it.

            file (`str` | `file`, optional):
                The output file path, directory, or stream-like object.
                If the path exists and is a file, it will be overwritten.
                If file is the type `bytes`, it will be downloaded in-memory
                as a bytestring (e.g. ``file=bytes``).

            download_big (`bool`, optional):
                Whether to use the big version of the available photos.

        Returns:
            ``None`` if no photo was provided, or if it was Empty. On success
            the file path is returned since it may differ from the one given.
        """
        # hex(crc32(x.encode('ascii'))) for x in
        # ('User', 'Chat', 'UserFull', 'ChatFull')
        ENTITIES = (0x2da17977, 0xc5af5d94, 0x1f4661b9, 0xd49a2697)
        # ('InputPeer', 'InputUser', 'InputChannel')
        INPUTS = (0xc91c90b6, 0xe669bf46, 0x40f202fd)
        if not isinstance(entity, TLObject) or entity.SUBCLASS_OF_ID in INPUTS:
            entity = await self.get_entity(entity)

        thumb = -1 if download_big else 0

        possible_names = []
        if entity.SUBCLASS_OF_ID not in ENTITIES:
            photo = entity
        else:
            if not hasattr(entity, 'photo'):
                # Special case: may be a ChatFull with photo:Photo
                # This is different from a normal UserProfilePhoto and Chat
                if not hasattr(entity, 'chat_photo'):
                    return None

                return await self._download_photo(
                    entity.chat_photo, file, date=None,
                    thumb=thumb, progress_callback=None
                )

            for attr in ('username', 'first_name', 'title'):
                possible_names.append(getattr(entity, attr, None))

            photo = entity.photo

        if isinstance(photo, (types.UserProfilePhoto, types.ChatPhoto)):
            dc_id = photo.dc_id
            which = photo.photo_big if download_big else photo.photo_small
            loc = types.InputPeerPhotoFileLocation(
                peer=await self.get_input_entity(entity),
                local_id=which.local_id,
                volume_id=which.volume_id,
                big=download_big
            )
        else:
            # It doesn't make any sense to check if `photo` can be used
            # as input location, because then this method would be able
            # to "download the profile photo of a message", i.e. its
            # media which should be done with `download_media` instead.
            return None

        file = self._get_proper_filename(
            file, 'profile_photo', '.jpg',
            possible_names=possible_names
        )

        try:
            result = await self.download_file(loc, file, dc_id=dc_id)
            return result if file is bytes else file
        except errors.LocationInvalidError:
            # See issue #500, Android app fails as of v4.6.0 (1155).
            # The fix seems to be using the full channel chat photo.
            ie = await self.get_input_entity(entity)
            if isinstance(ie, types.InputPeerChannel):
                full = await self(functions.channels.GetFullChannelRequest(ie))
                return await self._download_photo(
                    full.full_chat.chat_photo, file,
                    date=None, progress_callback=None,
                    thumb=thumb
                )
            else:
                # Until there's a report for chats, no need to.
                return None

    async def download_media(
            self: 'TelegramClient',
            message: hints.MessageLike,
            file: hints.FileLike = None,
            *,
            thumb: hints.FileLike = None,
            progress_callback: hints.ProgressCallback = None) -> typing.Optional[str]:
        """
        Downloads the given media, or the media from a specified Message.

        Note that if the download is too slow, you should consider installing
        ``cryptg`` (through ``pip install cryptg``) so that decrypting the
        received data is done in C instead of Python (much faster).

        message (`Message <telethon.tl.custom.message.Message>` | :tl:`Media`):
            The media or message containing the media that will be downloaded.

        file (`str` | `file`, optional):
            The output file path, directory, or stream-like object.
            If the path exists and is a file, it will be overwritten.
            If file is the type `bytes`, it will be downloaded in-memory
            as a bytestring (e.g. ``file=bytes``).

        progress_callback (`callable`, optional):
            A callback function accepting two parameters:
            ``(received bytes, total)``.

        thumb (`int` | :tl:`PhotoSize`, optional):
            Which thumbnail size from the document or photo to download,
            instead of downloading the document or photo itself.

            If it's specified but the file does not have a thumbnail,
            this method will return ``None``.

            The parameter should be an integer index between ``0`` and
            ``len(sizes)``. ``0`` will download the smallest thumbnail,
            and ``len(sizes) - 1`` will download the largest thumbnail.
            You can also use negative indices.

            You can also pass the :tl:`PhotoSize` instance to use.

            In short, use ``thumb=0`` if you want the smallest thumbnail
            and ``thumb=-1`` if you want the largest thumbnail.

        Returns:
            ``None`` if no media was provided, or if it was Empty. On success
            the file path is returned since it may differ from the one given.
        """
        # TODO This won't work for messageService
        if isinstance(message, types.Message):
            date = message.date
            media = message.media
        else:
            date = datetime.datetime.now()
            media = message

        if isinstance(media, str):
            media = utils.resolve_bot_file_id(media)

        if isinstance(media, types.MessageMediaWebPage):
            if isinstance(media.webpage, types.WebPage):
                media = media.webpage.document or media.webpage.photo

        if isinstance(media, (types.MessageMediaPhoto, types.Photo)):
            return await self._download_photo(
                media, file, date, thumb, progress_callback
            )
        elif isinstance(media, (types.MessageMediaDocument, types.Document)):
            return await self._download_document(
                media, file, date, thumb, progress_callback
            )
        elif isinstance(media, types.MessageMediaContact) and thumb is None:
            return self._download_contact(
                media, file
            )
        elif isinstance(media, (types.WebDocument, types.WebDocumentNoProxy)) and thumb is None:
            return await self._download_web_document(
                media, file, progress_callback
            )

    async def download_file(
            self: 'TelegramClient',
            input_location: hints.FileLike,
            file: hints.OutFileLike = None,
            *,
            part_size_kb: float = None,
            file_size: int = None,
            progress_callback: hints.ProgressCallback = None,
            dc_id: int = None) -> None:
        """
        Downloads the given input location to a file.

        Args:
            input_location (:tl:`InputFileLocation`):
                The file location from which the file will be downloaded.
                See `telethon.utils.get_input_location` source for a complete
                list of supported types.

            file (`str` | `file`, optional):
                The output file path, directory, or stream-like object.
                If the path exists and is a file, it will be overwritten.

                If the file path is ``None`` or ``bytes``, then the result
                will be saved in memory and returned as `bytes`.

            part_size_kb (`int`, optional):
                Chunk size when downloading files. The larger, the less
                requests will be made (up to 512KB maximum).

            file_size (`int`, optional):
                The file size that is about to be downloaded, if known.
                Only used if ``progress_callback`` is specified.

            progress_callback (`callable`, optional):
                A callback function accepting two parameters:
                ``(downloaded bytes, total)``. Note that the
                ``total`` is the provided ``file_size``.

            dc_id (`int`, optional):
                The data center the library should connect to in order
                to download the file. You shouldn't worry about this.
        """
        if not part_size_kb:
            if not file_size:
                part_size_kb = 64  # Reasonable default
            else:
                part_size_kb = utils.get_appropriated_part_size(file_size)

        part_size = int(part_size_kb * 1024)
        # https://core.telegram.org/api/files says:
        # > part_size % 1024 = 0 (divisible by 1KB)
        #
        # But https://core.telegram.org/cdn (more recent) says:
        # > limit must be divisible by 4096 bytes
        # So we just stick to the 4096 limit.
        if part_size % 4096 != 0:
            raise ValueError(
                'The part size must be evenly divisible by 4096.')

        in_memory = file is None or file is bytes
        if in_memory:
            f = io.BytesIO()
        elif isinstance(file, str):
            # Ensure that we'll be able to download the media
            helpers.ensure_parent_dir_exists(file)
            f = open(file, 'wb')
        else:
            f = file

        old_dc = dc_id
        dc_id, input_location = utils.get_input_location(input_location)
        if dc_id is None:
            dc_id = old_dc

        exported = dc_id and self.session.dc_id != dc_id
        if exported:
            try:
                sender = await self._borrow_exported_sender(dc_id)
            except errors.DcIdInvalidError:
                # Can't export a sender for the ID we are currently in
                config = await self(functions.help.GetConfigRequest())
                for option in config.dc_options:
                    if option.ip_address == self.session.server_address:
                        self.session.set_dc(
                            option.id, option.ip_address, option.port)
                        self.session.save()
                        break

                # TODO Figure out why the session may have the wrong DC ID
                sender = self._sender
                exported = False
        else:
            # The used sender will also change if ``FileMigrateError`` occurs
            sender = self._sender

        self._log[__name__].info('Downloading file in chunks of %d bytes',
                                 part_size)
        try:
            offset = 0
            while True:
                try:
                    result = await sender.send(functions.upload.GetFileRequest(
                        input_location, offset, part_size
                    ))
                    if isinstance(result, types.upload.FileCdnRedirect):
                        # TODO Implement
                        raise NotImplementedError
                except errors.FileMigrateError as e:
                    self._log[__name__].info('File lives in another DC')
                    sender = await self._borrow_exported_sender(e.new_dc)
                    exported = True
                    continue

                offset += part_size
                if not result.bytes:
                    if in_memory:
                        f.flush()
                        return f.getvalue()
                    else:
                        return getattr(result, 'type', '')

                self._log[__name__].debug('Saving %d more bytes',
                                          len(result.bytes))
                f.write(result.bytes)
                if progress_callback:
                    progress_callback(f.tell(), file_size)
        finally:
            if exported:
                await self._return_exported_sender(sender)
            elif sender != self._sender:
                await sender.disconnect()
            if isinstance(file, str) or in_memory:
                f.close()

    # endregion

    # region Private methods

    @staticmethod
    def _get_thumb(thumbs, thumb):
        if thumb is None:
            return thumbs[-1]
        elif isinstance(thumb, int):
            return thumbs[thumb]
        elif isinstance(thumb, (types.PhotoSize, types.PhotoCachedSize,
                                types.PhotoStrippedSize)):
            return thumb
        else:
            return None

    def _download_cached_photo_size(self: 'TelegramClient', size, file):
        # No need to download anything, simply write the bytes
        if file is bytes:
            return size.bytes
        elif isinstance(file, str):
            helpers.ensure_parent_dir_exists(file)
            f = open(file, 'wb')
        else:
            f = file

        try:
            f.write(utils.stripped_photo_to_jpg(size.bytes)
                    if isinstance(size, types.PhotoStrippedSize)
                    else size.bytes)
        finally:
            if isinstance(file, str):
                f.close()
        return file

    async def _download_photo(self: 'TelegramClient', photo, file, date, thumb, progress_callback):
        """Specialized version of .download_media() for photos"""
        # Determine the photo and its largest size
        if isinstance(photo, types.MessageMediaPhoto):
            photo = photo.photo
        if not isinstance(photo, types.Photo):
            return

        size = self._get_thumb(photo.sizes, thumb)
        if not size or isinstance(size, types.PhotoSizeEmpty):
            return

        file = self._get_proper_filename(file, 'photo', '.jpg', date=date)
        if isinstance(size, (types.PhotoCachedSize, types.PhotoStrippedSize)):
            return self._download_cached_photo_size(size, file)

        result = await self.download_file(
            types.InputPhotoFileLocation(
                id=photo.id,
                access_hash=photo.access_hash,
                file_reference=photo.file_reference,
                thumb_size=size.type
            ),
            file,
            file_size=size.size,
            progress_callback=progress_callback
        )
        return result if file is bytes else file

    @staticmethod
    def _get_kind_and_names(attributes):
        """Gets kind and possible names for :tl:`DocumentAttribute`."""
        kind = 'document'
        possible_names = []
        for attr in attributes:
            if isinstance(attr, types.DocumentAttributeFilename):
                possible_names.insert(0, attr.file_name)

            elif isinstance(attr, types.DocumentAttributeAudio):
                kind = 'audio'
                if attr.performer and attr.title:
                    possible_names.append('{} - {}'.format(
                        attr.performer, attr.title
                    ))
                elif attr.performer:
                    possible_names.append(attr.performer)
                elif attr.title:
                    possible_names.append(attr.title)
                elif attr.voice:
                    kind = 'voice'

        return kind, possible_names

    async def _download_document(
            self, document, file, date, thumb, progress_callback):
        """Specialized version of .download_media() for documents."""
        if isinstance(document, types.MessageMediaDocument):
            document = document.document
        if not isinstance(document, types.Document):
            return

        kind, possible_names = self._get_kind_and_names(document.attributes)
        file = self._get_proper_filename(
            file, kind, utils.get_extension(document),
            date=date, possible_names=possible_names
        )

        if thumb is None:
            size = None
        else:
            size = self._get_thumb(document.thumbs, thumb)
            if isinstance(size, (types.PhotoCachedSize, types.PhotoStrippedSize)):
                return self._download_cached_photo_size(size, file)

        result = await self.download_file(
            types.InputDocumentFileLocation(
                id=document.id,
                access_hash=document.access_hash,
                file_reference=document.file_reference,
                thumb_size=size.type if size else ''
            ),
            file,
            file_size=size.size if size else document.size,
            progress_callback=progress_callback
        )

        return result if file is bytes else file

    @classmethod
    def _download_contact(cls, mm_contact, file):
        """
        Specialized version of .download_media() for contacts.
        Will make use of the vCard 4.0 format.
        """
        first_name = mm_contact.first_name
        last_name = mm_contact.last_name
        phone_number = mm_contact.phone_number

        # Remove these pesky characters
        first_name = first_name.replace(';', '')
        last_name = (last_name or '').replace(';', '')
        result = (
            'BEGIN:VCARD\n'
            'VERSION:4.0\n'
            'N:{f};{l};;;\n'
            'FN:{f} {l}\n'
            'TEL;TYPE=cell;VALUE=uri:tel:+{p}\n'
            'END:VCARD\n'
        ).format(f=first_name, l=last_name, p=phone_number).encode('utf-8')

        if file is bytes:
            return result
        elif isinstance(file, str):
            file = cls._get_proper_filename(
                file, 'contact', '.vcard',
                possible_names=[first_name, phone_number, last_name]
            )
            f = open(file, 'wb', encoding='utf-8')
        else:
            f = file

        try:
            f.write(result)
        finally:
            # Only close the stream if we opened it
            if isinstance(file, str):
                f.close()

        return file

    @classmethod
    async def _download_web_document(cls, web, file, progress_callback):
        """
        Specialized version of .download_media() for web documents.
        """
        if not aiohttp:
            raise ValueError(
                'Cannot download web documents without the aiohttp '
                'dependency install it (pip install aiohttp)'
            )

        # TODO Better way to get opened handles of files and auto-close
        in_memory = file is bytes
        if in_memory:
            f = io.BytesIO()
        elif isinstance(file, str):
            kind, possible_names = cls._get_kind_and_names(web.attributes)
            file = cls._get_proper_filename(
                file, kind, utils.get_extension(web),
                possible_names=possible_names
            )
            f = open(file, 'wb')
        else:
            f = file

        try:
            with aiohttp.ClientSession() as session:
                # TODO Use progress_callback; get content length from response
                # https://github.com/telegramdesktop/tdesktop/blob/c7e773dd9aeba94e2be48c032edc9a78bb50234e/Telegram/SourceFiles/ui/images.cpp#L1318-L1319
                async with session.get(web.url) as response:
                    while True:
                        chunk = await response.content.read(128 * 1024)
                        if not chunk:
                            break
                        f.write(chunk)
        finally:
            if isinstance(file, str) or file is bytes:
                f.close()

        return f.getvalue() if in_memory else file

    @staticmethod
    def _get_proper_filename(file, kind, extension,
                             date=None, possible_names=None):
        """Gets a proper filename for 'file', if this is a path.

           'kind' should be the kind of the output file (photo, document...)
           'extension' should be the extension to be added to the file if
                       the filename doesn't have any yet
           'date' should be when this file was originally sent, if known
           'possible_names' should be an ordered list of possible names

           If no modification is made to the path, any existing file
           will be overwritten.
           If any modification is made to the path, this method will
           ensure that no existing file will be overwritten.
        """
        if isinstance(file, pathlib.Path):
            file = str(file.absolute())

        if file is not None and not isinstance(file, str):
            # Probably a stream-like object, we cannot set a filename here
            return file

        if file is None:
            file = ''
        elif os.path.isfile(file):
            # Make no modifications to valid existing paths
            return file

        if os.path.isdir(file) or not file:
            try:
                name = None if possible_names is None else next(
                    x for x in possible_names if x
                )
            except StopIteration:
                name = None

            if not name:
                if not date:
                    date = datetime.datetime.now()
                name = '{}_{}-{:02}-{:02}_{:02}-{:02}-{:02}'.format(
                    kind,
                    date.year, date.month, date.day,
                    date.hour, date.minute, date.second,
                )
            file = os.path.join(file, name)

        directory, name = os.path.split(file)
        name, ext = os.path.splitext(name)
        if not ext:
            ext = extension

        result = os.path.join(directory, name + ext)
        if not os.path.isfile(result):
            return result

        i = 1
        while True:
            result = os.path.join(directory, '{} ({}){}'.format(name, i, ext))
            if not os.path.isfile(result):
                return result
            i += 1

    # endregion
