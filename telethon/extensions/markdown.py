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

def tg_string_len(s):
    return len(s.encode('utf-16le')) // 2

class Mode(Enum):
    """Different modes supported by Telegram's Markdown"""
    NONE = 0
    BOLD = 1
    ITALIC = 2
    CODE = 3
    PRE = 4
    URL = 5


DEFAULT_DELIMITERS = {
    '**': Mode.BOLD,
    '__': Mode.ITALIC,
    '`': Mode.CODE,
    '```': Mode.PRE
}

DEFAULT_URL_RE = re.compile(r'\[(.+?)\]\((.+?)\)')

def parse(message, delimiters=None, url_re=None):
    """
    Parses the given message and returns the stripped message and a list
    of tuples containing (start, end, mode) using the specified delimiters
    dictionary (or default if None).

    The url_re(gex) must contain two matching groups: the text to be
    clickable and the URL itself.
    """
    if url_re is None:
        url_re = DEFAULT_URL_RE
    elif url_re:
        if isinstance(url_re, str):
            url_re = re.compile(url_re)

    if not delimiters:
        if delimiters is not None:
            return message, []
        delimiters = DEFAULT_DELIMITERS

    result = []
    current = Mode.NONE
    offset = 0
    i = 0
    while i < len(message):
        url_match = None
        if url_re and current == Mode.NONE:
            url_match = url_re.match(message, pos=i)
            if url_match:
                message = ''.join((
                    message[:url_match.start()],
                    url_match.group(1),
                    message[url_match.end():]
                ))

                result.append((
                    offset,
                    offset + tg_string_len(url_match.group(1)),
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
            offset += tg_string_len(message[i])
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
