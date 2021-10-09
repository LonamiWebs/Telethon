import mimetypes
import os
import pathlib

from ... import _tl


class InputFile:
    def __init__(
            self,
            file = None,
            *,
            file_name: str = None,
            mime_type: str = None,
            thumb: str = False,
            force_file: bool = False,
            file_size: int = None,
            duration: int = None,
            width: int = None,
            height: int = None,
            title: str = None,
            performer: str = None,
            supports_streaming: bool = False,
            video_note: bool = False,
            voice_note: bool = False,
            waveform: bytes = None,
            ttl: int = None,
    ):
        if isinstance(file, pathlib.Path):
            if not file_name:
                file_name = file.name
            file = str(file.absolute())
        elif not file_name:
            if isinstance(file, str):
                file_name = os.path.basename(file)
            else:
                file_name = getattr(file, 'name', 'unnamed')

        if not mime_type:
            mime_type = mimetypes.guess_type(file_name)[0] or 'application/octet-stream'

        mime_type = mime_type.lower()

        attributes = [_tl.DocumentAttributeFilename(file_name)]

        # TODO hachoir or tinytag or ffmpeg
        if mime_type.startswith('image'):
            if width is not None and height is not None:
                attributes.append(_tl.DocumentAttributeImageSize(
                    w=width,
                    h=height,
                ))
        elif mime_type.startswith('audio'):
            attributes.append(_tl.DocumentAttributeAudio(
                duration=duration,
                voice=voice_note,
                title=title,
                performer=performer,
                waveform=waveform,
            ))
        elif mime_type.startswith('video'):
            attributes.append(_tl.DocumentAttributeVideo(
                duration=duration,
                w=width,
                h=height,
                round_message=video_note,
                supports_streaming=supports_streaming,
            ))

        # mime_type: str = None,
        # thumb: str = False,
        # force_file: bool = False,
        # file_size: int = None,
        # ttl: int = None,

        self._file = file
        self._attributes = attributes


        # TODO rest

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

        if media:
            pass  # Already have media, don't check the rest
        elif not file_handle:
            raise ValueError(
                'Failed to convert {} to media. Not an existing file or '
                'HTTP URL'.format(file)
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






