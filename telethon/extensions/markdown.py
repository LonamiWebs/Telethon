"""
Simple markdown parser which does not support nesting. Intended primarily
for use within the library, which attempts to handle emojies correctly,
since they seem to count as two characters and it's a bit strange.
"""
import re
from enum import Enum

from ..tl.types import (
    MessageEntityBold, MessageEntityItalic, MessageEntityCode, MessageEntityPre
)


class Mode(Enum):
    """Different modes supported by Telegram's Markdown"""
    NONE = 0
    BOLD = 1
    ITALIC = 2
    CODE = 3
    PRE = 4


EMOJI_PATTERN = re.compile(
    '['
    '\U0001F600-\U0001F64F'  # emoticons
    '\U0001F300-\U0001F5FF'  # symbols & pictographs
    '\U0001F680-\U0001F6FF'  # transport & map symbols
    '\U0001F1E0-\U0001F1FF'  # flags (iOS)
    ']+', flags=re.UNICODE
)


def is_emoji(char):
    """Returns True if 'char' looks like an emoji"""
    return bool(EMOJI_PATTERN.match(char))


def emojiness(char):
    """
    Returns the "emojiness" of an emoji, or how many characters it counts as.
    1 if it's not an emoji, 2 usual, 3 "special" (seem to count more).
    """
    if not is_emoji(char):
        return 1
    if ord(char) < ord('🤐'):
        return 2
    else:
        return 3


def parse(message, delimiters=None):
    """
    Parses the given message and returns the stripped message and a list
    of tuples containing (start, end, mode) using the specified delimiters
    dictionary (or default if None).
    """
    if not delimiters:
        if delimiters is not None:
            return message, []

        delimiters = {
            '**': Mode.BOLD,
            '__': Mode.ITALIC,
            '`': Mode.CODE,
            '```': Mode.PRE
        }

    result = []
    current = Mode.NONE
    offset = 0
    i = 0
    while i < len(message):
        for d, m in delimiters.items():
            if message[i:i + len(d)] == d and current in (Mode.NONE, m):
                if message[i + len(d):i + 2 * len(d)] == d:
                    continue  # ignore two consecutive delimiters

                message = message[:i] + message[i + len(d):]
                if current == Mode.NONE:
                    result.append(offset)
                    current = m
                else:
                    result[-1] = (result[-1], offset, current)
                    current = Mode.NONE
                break

        if i < len(message):
            offset += emojiness(message[i])
            i += 1

    if result and not isinstance(result[-1], tuple):
        result.pop()
    return message, result


def parse_tg(message, delimiters=None):
    """Similar to parse(), but returns a list of MessageEntity's"""
    message, tuples = parse(message, delimiters=delimiters)
    result = []
    for start, end, mode in tuples:
        if mode == Mode.BOLD:
            result.append(MessageEntityBold(start, end - start))
        elif mode == Mode.ITALIC:
            result.append(MessageEntityItalic(start, end - start))
        elif mode == Mode.CODE:
            result.append(MessageEntityCode(start, end - start))
        elif mode == Mode.PRE:
            result.append(MessageEntityPre(start, end - start, ''))
    return message, result
