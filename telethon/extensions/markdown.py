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


DEFAULT_DELIMITERS = {
    '**': Mode.BOLD,
    '__': Mode.ITALIC,
    '`': Mode.CODE,
    '```': Mode.PRE
}

# Regex used to match utf-16le encoded r'\[(.+?)\]\((.+?)\)',
# reason why there's '\0' after every match-literal character.
DEFAULT_URL_RE = re.compile(b'\\[\0(.+)\\]\0\\(\0(.+?)\\)\0')


def parse(message, delimiters=None, url_re=None):
    """
    Parses the given message and returns the stripped message and a list
    of tuples containing (start, end, mode) using the specified delimiters
    dictionary (or default if None).

    The url_re(gex) must contain two matching groups: the text to be
    clickable and the URL itself, and be utf-16le encoded.
    """
    # Work on byte level with the utf-16le encoding to get the offsets right.
    # The offset will just be half the index we're at.
    if url_re is None:
        url_re = DEFAULT_URL_RE
    elif url_re:
        if isinstance(url_re, str):
            url_re = re.compile(url_re.encode('utf-16le'))

    if not delimiters:
        if delimiters is not None:
            return message, []
        delimiters = DEFAULT_DELIMITERS

    delimiters = {k.encode('utf-16le'): v for k, v in delimiters.items()}

    i = 0
    result = []
    current = Mode.NONE
    message = message.encode('utf-16le')
    while i < len(message):
        url_match = None
        if url_re and current == Mode.NONE:
            url_match = url_re.match(message, pos=i)
            if url_match:
                message = b''.join((
                    message[:url_match.start()],
                    url_match.group(1),
                    message[url_match.end():]
                ))

                result.append((
                    i // 2,
                    (i + len(url_match.group(1))) // 2,
                    (Mode.URL, url_match.group(2).decode('utf-16le'))
                ))
                # We matched the delimiter which is now gone, and we'll add
                # +2 before next iteration which will make us skip a character.
                # Go back by one utf-16 encoded character (-2) to avoid it.
                i += len(url_match.group(1)) - 2

        if not url_match:
            for d, m in delimiters.items():
                if message[i:i + len(d)] == d and current in (Mode.NONE, m):
                    if message[i + len(d):i + 2 * len(d)] == d:
                        continue  # ignore two consecutive delimiters

                    message = message[:i] + message[i + len(d):]
                    if current == Mode.NONE:
                        result.append(i // 2)
                        current = m
                        # No need to i -= 2 here because it's been already
                        # checked that next character won't be a delimiter.
                    else:
                        result[-1] = (result[-1], i // 2, current)
                        current = Mode.NONE
                        i -= 2  # Delimiter matched and gone, go back 1 char
                    break

        if i < len(message):
            i += 2

    if result and not isinstance(result[-1], tuple):
        result.pop()

    return message.decode('utf-16le'), result


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
