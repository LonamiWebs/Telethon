from typing import Optional
from .inputfile import InputFile
from ... import _misc
from .button import build_reply_markup


class InputMessage:
    __slots__ = (
        '_text',
        '_link_preview',
        '_silent',
        '_reply_markup',
        '_fmt_entities',
        '_file',
    )

    _default_parse_mode = (lambda t: (t, []), lambda t, e: t)
    _default_link_preview = True

    def __init__(
            self,
            text: str = None,
            *,
            markdown: str = None,
            html: str = None,
            formatting_entities: list = None,
            link_preview: bool = (),
            file=None,
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
            silent: bool = False,
            buttons: list = None,
            ttl: int = None,
            parse_fn = None,
    ):
        if (text and markdown) or (text and html) or (markdown and html):
            raise ValueError('can only set one of: text, markdown, html')

        if formatting_entities:
            text = text or markdown or html
        elif text:
            text, formatting_entities = self._default_parse_mode[0](text)
        elif markdown:
            text, formatting_entities = _misc.markdown.parse(markdown)
        elif html:
            text, formatting_entities = _misc.html.parse(html)

        reply_markup = build_reply_markup(buttons) if buttons else None

        if not text:
            text = ''
        if not formatting_entities:
            formatting_entities = None

        if link_preview == ():
            link_preview = self._default_link_preview

        if file and not isinstance(file, InputFile):
            file = InputFile(
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
            )

        self._text = text
        self._link_preview = link_preview
        self._silent = silent
        self._reply_markup = reply_markup
        self._fmt_entities = formatting_entities
        self._file = file

    # oh! when this message is used, the file can be cached in here! if not inputfile upload and set inputfile
