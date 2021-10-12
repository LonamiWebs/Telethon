import mimetypes
import os
import re
import time

from pathlib import Path

from ... import _tl
from ..._misc import utils


class InputFile:
    # Expected Time-To-Live for _uploaded_*.
    # After this period they should be reuploaded.
    # Telegram's limit are unknown, so this value is conservative.
    UPLOAD_TTL = 8 * 60 * 60

    __slots__ = (
        # main media
        '_file',  # can reupload
        '_media',  # can only use as-is
        '_uploaded_file',  # (input file, timestamp)
        # thumbnail
        '_thumb',  # can reupload
        '_uploaded_thumb',  # (input file, timestamp)
        # document parameters
        '_mime_type',
        '_attributes',
        '_video_note',
        '_force_file',
        '_ttl',
    )

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
        # main media
        self._file =  None
        self._media = None
        self._uploaded_file = None

        if isinstance(file, str) and re.match('https?://', file, flags=re.IGNORECASE):
            if not force_file and mime_type.startswith('image'):
                self._media = _tl.InputMediaPhotoExternal(file, ttl_seconds=ttl)
            else:
                self._media = _tl.InputMediaDocumentExternal(file, ttl_seconds=ttl)

        elif isinstance(file, (str, bytes, Path)) or callable(getattr(file, 'read', None)):
            self._file = file

        elif isinstance(file, (_tl.InputFile, _tl.InputFileBig)):
            self._uploaded_file = (file, time.time())

        else:
            self._media = utils.get_input_media(
                file,
                is_photo=not force_file and mime_type.startswith('image'),
                attributes=[],
                force_document=force_file,
                voice_note=voice_note,
                video_note=video_note,
                supports_streaming=supports_streaming,
                ttl=ttl
            )

        # thumbnail
        self._thumb = None
        self._uploaded_thumb = None

        if isinstance(thumb, (str, bytes, Path)) or callable(getattr(thumb, 'read', None)):
            self._thumb = thumb

        elif isinstance(thumb, (_tl.InputFile, _tl.InputFileBig)):
            self._uploaded_thumb = (thumb, time.time())

        else:
            raise TypeError(f'thumb must be a file to upload, but got: {thumb!r}')

        # document parameters (only if it's our file, i.e. there's no media ready yet)
        if self._media:
            self._mime_type = None
            self._attributes = None
            self._video_note = None
            self._force_file = None
            self._ttl = None
        else:
            if isinstance(file, Path):
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

            self._mime_type = mime_type
            self._attributes = attributes
            self._video_note = video_note
            self._force_file = force_file
            self._ttl = ttl

    def _should_upload_thumb(self):
        return self._thumb and (
            not self._uploaded_thumb
            or time.time() > self._uploaded_thumb[1] + InputFile.UPLOAD_TTL)

    def _should_upload_file(self):
        return self._file and (
            not self._uploaded_file
            or time.time() > self._uploaded_file[1] + InputFile.UPLOAD_TTL)

    def _set_uploaded_thumb(self, input_file):
        self._uploaded_thumb = (input_file, time.time())

    def _set_uploaded_file(self, input_file):
        if not self._force_file and self._mime_type.startswith('image'):
            self._media = _tl.InputMediaUploadedPhoto(input_file, ttl_seconds=self._ttl)
        else:
            self._media = _tl.InputMediaUploadedDocument(
                file=input_file,
                mime_type=self._mime_type,
                attributes=self._attributes,
                thumb=self._uploaded_thumb[0] if self._uploaded_thumb else None,
                force_file=self._force_file,
                ttl_seconds=self._ttl,
            )
