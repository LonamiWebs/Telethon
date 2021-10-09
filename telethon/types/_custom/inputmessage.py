
class InputMessage:
    __slots__ = (
        '_text',
        '_link_preview',
        '_silent',
        '_reply_markup',
        '_fmt_entities',
        '_file',
    )

    def __init__(
            self,
            text,
            *,
            link_preview,
            silent,
            reply_markup,
            fmt_entities,
            file,
    ):
        self._text = text
        self._link_preview = link_preview
        self._silent = silent
        self._reply_markup = reply_markup
        self._fmt_entities = fmt_entities
        self._file = file

    # oh! when this message is used, the file can be cached in here! if not inputfile upload and set inputfile
