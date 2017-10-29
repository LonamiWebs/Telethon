"""
Simple markdown parser which does not support nesting. Intended primarily
for use within the library, which attempts to handle emojies correctly,
since they seem to count as two characters and it's a bit strange.
"""
import re
from enum import Enum

from ..tl.types import (
    MessageEntityBold, MessageEntityItalic, MessageEntityCode,
    MessageEntityPre, MessageEntityTextUrl
)


class Mode(Enum):
    """Different modes supported by Telegram's Markdown"""
    NONE = 0
    BOLD = 1
    ITALIC = 2
    CODE = 3
    PRE = 4
    URL = 5


# using telethon_generator/emoji_ranges.py
EMOJI_RANGES = (
    (8596, 8601), (8617, 8618), (8986, 8987), (9193, 9203), (9208, 9210),
    (9642, 9643), (9723, 9726), (9728, 9733), (9735, 9746), (9748, 9751),
    (9754, 9884), (9886, 9905), (9907, 9953), (9956, 9983), (9985, 9988),
    (9992, 10002), (10035, 10036), (10067, 10069), (10083, 10087),
    (10133, 10135), (10548, 10549), (11013, 11015), (11035, 11036),
    (126976, 127166), (127169, 127183), (127185, 127231), (127245, 127247),
    (127340, 127345), (127358, 127359), (127377, 127386), (127405, 127487),
    (127489, 127503), (127538, 127546), (127548, 127551), (127561, 128419),
    (128421, 128591), (128640, 128767), (128884, 128895), (128981, 129023),
    (129036, 129039), (129096, 129103), (129114, 129119), (129160, 129167),
    (129198, 129338), (129340, 129342), (129344, 129349), (129351, 129355),
    (129357, 129471), (129473, 131069)
)


def is_emoji(char):
    """Returns True if 'char' looks like an emoji"""
    char = ord(char)
    for start, end in EMOJI_RANGES:
        if start <= char <= end:
            return True
    return False


def emojiness(char):
    """
    Returns the "emojiness" of an emoji, or how many characters it counts as.
    1 if it's not an emoji, 2 usual, 3 "special" (seem to count more).
    """
    if not is_emoji(char):
        return 1
    if ord(char) < 129296:
        return 2
    else:
        return 3


def parse(message, delimiters=None, url_re=r'\[(.+?)\]\((.+?)\)'):
    """
    Parses the given message and returns the stripped message and a list
    of tuples containing (start, end, mode) using the specified delimiters
    dictionary (or default if None).

    The url_re(gex) must contain two matching groups: the text to be
    clickable and the URL itself.
    """
    if url_re:
        if isinstance(url_re, str):
            url_re = re.compile(url_re)

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
        url_match = None
        if current == Mode.NONE:
            url_match = url_re.match(message, pos=i)
            if url_match:
                message = ''.join((
                    message[:url_match.start()],
                    url_match.group(1),
                    message[url_match.end():]
                ))
                emoji_len = sum(emojiness(c) for c in url_match.group(1))
                result.append((
                    offset,
                    i + emoji_len,
                    (Mode.URL, url_match.group(2))
                ))
                i += len(url_match.group(1))
        if not url_match:
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
        extra = None
        if isinstance(mode, tuple):
            mode, extra = mode

        if mode == Mode.BOLD:
            result.append(MessageEntityBold(start, end - start))
        elif mode == Mode.ITALIC:
            result.append(MessageEntityItalic(start, end - start))
        elif mode == Mode.CODE:
            result.append(MessageEntityCode(start, end - start))
        elif mode == Mode.PRE:
            result.append(MessageEntityPre(start, end - start, ''))
        elif mode == Mode.URL:
            result.append(MessageEntityTextUrl(start, end - start, extra))
    return message, result
