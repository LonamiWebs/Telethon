from .updates import UpdateMethods
from ..tl import types, custom
from .. import utils, events


class ButtonMethods(UpdateMethods):
    def build_reply_markup(self, buttons, inline_only=False):
        """
        Builds a :tl`ReplyInlineMarkup` or :tl:`ReplyKeyboardMarkup` for
        the given buttons, or does nothing if either no buttons are
        provided or the provided argument is already a reply markup.

        This will add any event handlers defined in the
        buttons and delete old ones not to call them twice,
        so you should probably call this method manually for
        serious bots instead re-adding handlers every time you
        send a message. Magic can only go so far.
        """
        if buttons is None:
            return None

        try:
            if buttons.SUBCLASS_OF_ID == 0xe2e10ef2:
                return buttons  # crc32(b'ReplyMarkup'):
        except AttributeError:
            pass

        if not utils.is_list_like(buttons):
            buttons = [[buttons]]
        elif not utils.is_list_like(buttons[0]):
            buttons = [buttons]

        is_inline = False
        is_normal = False

        rows = []
        for row in buttons:
            current = []
            for button in row:
                inline = custom.Button._is_inline(button)
                is_inline |= inline
                is_normal |= not inline
                if isinstance(button, custom.Button):
                    if button.callback:
                        self.remove_event_handler(
                            button.callback, events.CallbackQuery)

                        self.add_event_handler(
                            button.callback,
                            events.CallbackQuery(data=getattr(
                                button.button, 'data', None))
                        )

                    button = button.button
                elif isinstance(button, custom.MessageButton):
                    button = button.button

                if button.SUBCLASS_OF_ID == 0xbad74a3:
                    # 0xbad74a3 == crc32(b'KeyboardButton')
                    current.append(button)

            if current:
                rows.append(types.KeyboardButtonRow(current))

        if inline_only and is_normal:
            raise ValueError('You cannot use non-inline buttons here')
        elif is_inline == is_normal and is_normal:
            raise ValueError('You cannot mix inline with normal buttons')
        elif is_inline:
            return types.ReplyInlineMarkup(rows)
        elif is_normal:
            return types.ReplyKeyboardMarkup(rows)
