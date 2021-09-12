import typing

from .._misc import utils, hints
from .. import _tl
from .._tl import custom


def build_reply_markup(
        buttons: 'typing.Optional[hints.MarkupLike]',
        inline_only: bool = False) -> 'typing.Optional[_tl.TypeReplyMarkup]':
    if buttons is None:
        return None

    try:
        if buttons.SUBCLASS_OF_ID == 0xe2e10ef2:
            return buttons  # crc32(b'ReplyMarkup'):
    except AttributeError:
        pass

    if not utils.is_list_like(buttons):
        buttons = [[buttons]]
    elif not buttons or not utils.is_list_like(buttons[0]):
        buttons = [buttons]

    is_inline = False
    is_normal = False
    resize = None
    single_use = None
    selective = None

    rows = []
    for row in buttons:
        current = []
        for button in row:
            if isinstance(button, custom.Button):
                if button.resize is not None:
                    resize = button.resize
                if button.single_use is not None:
                    single_use = button.single_use
                if button.selective is not None:
                    selective = button.selective

                button = button.button
            elif isinstance(button, custom.MessageButton):
                button = button.button

            inline = custom.Button._is_inline(button)
            is_inline |= inline
            is_normal |= not inline

            if button.SUBCLASS_OF_ID == 0xbad74a3:
                # 0xbad74a3 == crc32(b'KeyboardButton')
                current.append(button)

        if current:
            rows.append(_tl.KeyboardButtonRow(current))

    if inline_only and is_normal:
        raise ValueError('You cannot use non-inline buttons here')
    elif is_inline == is_normal and is_normal:
        raise ValueError('You cannot mix inline with normal buttons')
    elif is_inline:
        return _tl.ReplyInlineMarkup(rows)
    # elif is_normal:
    return _tl.ReplyKeyboardMarkup(
        rows, resize=resize, single_use=single_use, selective=selective)
