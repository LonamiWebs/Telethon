import datetime
import io
import logging
import os
import pathlib

from .users import UserMethods
from .. import utils, helpers, errors
from ..tl import TLObject, types, functions

__log__ = logging.getLogger(__name__)


class DownloadMethods(UserMethods):

    # region Public methods

    async def download_profile_photo(
            self, entity, file=None, *, download_big=True):
        """
        Downloads the profile photo of the given entity (user/chat/channel).

        Args:
            entity (`entity`):
                From who the photo will be downloaded.

            file (`str` | `file`, optional):
                The output file path, directory, or stream-like object.
                If the path exists and is a file, it will be overwritten.

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
                    entity.chat_photo, file, date=None, progress_callback=None)

            for attr in ('username', 'first_name', 'title'):
                possible_names.append(getattr(entity, attr, None))

            photo = entity.photo

        if isinstance(photo, (types.UserProfilePhoto, types.ChatPhoto)):
            loc = photo.photo_big if download_big else photo.photo_small
        else:
            try:
                loc = utils.get_input_location(photo)
            except TypeError:
                return None

        file = self._get_proper_filename(
            file, 'profile_photo', '.jpg',
            possible_names=possible_names
        )

        try:
            await self.download_file(loc, file)
            return file
        except errors.LocationInvalidError:
            # See issue #500, Android app fails as of v4.6.0 (1155).
            # The fix seems to be using the full channel chat photo.
            ie = await self.get_input_entity(entity)
            if isinstance(ie, types.InputPeerChannel):
                full = await self(functions.channels.GetFullChannelRequest(ie))
                return await self._download_photo(
                    full.full_chat.chat_photo, file,
                    date=None, progress_callback=None
                )
            else:
                # Until there's a report for chats, no need to.
                return None

    async def download_media(self, message, file=None,
                             *, progress_callback=None):
        """
        Downloads the given media, or the media from a specified Message.

        Note that if the download is too slow, you should consider installing
        ``cryptg`` (through ``pip install cryptg``) so that decrypting the
        received data is done in C instead of Python (much faster).

        message (:tl:`Message` | :tl:`Media`):
            The media or message containing the media that will be downloaded.

        file (`str` | `file`, optional):
            The output file path, directory, or stream-like object.
            If the path exists and is a file, it will be overwritten.

        progress_callback (`callable`, optional):
            A callback function accepting two parameters:
            ``(received bytes, total)``.

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

        if isinstance(media, types.MessageMediaWebPage):
            if isinstance(media.webpage, types.WebPage):
                media = media.webpage.document or media.webpage.photo

        if isinstance(media, (types.MessageMediaPhoto, types.Photo,
                              types.PhotoSize, types.PhotoCachedSize)):
            return await self._download_photo(
                media, file, date, progress_callback
            )
        elif isinstance(media, (types.MessageMediaDocument, types.Document)):
            return await self._download_document(
                media, file, date, progress_callback
            )
        elif isinstance(media, types.MessageMediaContact):
            return self._download_contact(
                media, file
            )

    async def download_file(
            self, input_location, file=None, *, part_size_kb=None,
            file_size=None, progress_callback=None):
        """
        Downloads the given input location to a file.

        Args:
            input_location (:tl:`FileLocation` | :tl:`InputFileLocation`):
                The file location from which the file will be downloaded.
                See `telethon.utils.get_input_location` source for a complete
                list of supported types.

            file (`str` | `file`, optional):
                The output file path, directory, or stream-like object.
                If the path exists and is a file, it will be overwritten.

                If the file path is ``None``, then the result will be
                saved in memory and returned as `bytes`.

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

        in_memory = file is None
        if in_memory:
            f = io.BytesIO()
        elif isinstance(file, str):
            # Ensure that we'll be able to download the media
            helpers.ensure_parent_dir_exists(file)
            f = open(file, 'wb')
        else:
            f = file

        dc_id, input_location = utils.get_input_location(input_location)
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

        __log__.info('Downloading file in chunks of %d bytes', part_size)
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
                    __log__.info('File lives in another DC')
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

                __log__.debug('Saving %d more bytes', len(result.bytes))
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

    async def _download_photo(self, photo, file, date, progress_callback):
        """Specialized version of .download_media() for photos"""
        # Determine the photo and its largest size
        if isinstance(photo, types.MessageMediaPhoto):
            photo = photo.photo
        if isinstance(photo, types.Photo):
            for size in reversed(photo.sizes):
                if not isinstance(size, types.PhotoSizeEmpty):
                    photo = size
                    break
            else:
                return
        if not isinstance(photo, (types.PhotoSize, types.PhotoCachedSize)):
            return

        file = self._get_proper_filename(file, 'photo', '.jpg', date=date)
        if isinstance(photo, types.PhotoCachedSize):
            # No need to download anything, simply write the bytes
            if isinstance(file, str):
                helpers.ensure_parent_dir_exists(file)
                f = open(file, 'wb')
            else:
                f = file
            try:
                f.write(photo.bytes)
            finally:
                if isinstance(file, str):
                    f.close()
            return file

        await self.download_file(
            photo.location, file, file_size=photo.size,
            progress_callback=progress_callback)
        return file

    async def _download_document(
            self, document, file, date, progress_callback):
        """Specialized version of .download_media() for documents."""
        if isinstance(document, types.MessageMediaDocument):
            document = document.document
        if not isinstance(document, types.Document):
            return

        file_size = document.size

        kind = 'document'
        possible_names = []
        for attr in document.attributes:
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

        file = self._get_proper_filename(
            file, kind, utils.get_extension(document),
            date=date, possible_names=possible_names
        )

        await self.download_file(
            document, file, file_size=file_size,
            progress_callback=progress_callback)
        return file

    @classmethod
    def _download_contact(cls, mm_contact, file):
        """
        Specialized version of .download_media() for contacts.
        Will make use of the vCard 4.0 format.
        """
        first_name = mm_contact.first_name
        last_name = mm_contact.last_name
        phone_number = mm_contact.phone_number

        if isinstance(file, str):
            file = cls._get_proper_filename(
                file, 'contact', '.vcard',
                possible_names=[first_name, phone_number, last_name]
            )
            f = open(file, 'w', encoding='utf-8')
        else:
            f = file

        try:
            # Remove these pesky characters
            first_name = first_name.replace(';', '')
            last_name = (last_name or '').replace(';', '')
            f.write('BEGIN:VCARD\n')
            f.write('VERSION:4.0\n')
            f.write('N:{};{};;;\n'.format(first_name, last_name))
            f.write('FN:{} {}\n'.format(first_name, last_name))
            f.write('TEL;TYPE=cell;VALUE=uri:tel:+{}\n'.format(phone_number))
            f.write('END:VCARD\n')
        finally:
            # Only close the stream if we opened it
            if isinstance(file, str):
                f.close()

        return file

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
