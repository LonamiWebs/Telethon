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
DEFAULT_URL_RE = re.compile(b'\\[\0(.+?)\\]\0\\(\0(.+?)\\)\0')


def parse(message, delimiters=None, url_re=None):
    """
    Parses the given message and returns the stripped message and a list
    of tuples containing (start, end, mode) using the specified delimiters
    dictionary (or default if None).

    The url_re(gex) must contain two matching groups: the text to be
    clickable and the URL itself, and be utf-16le encoded.
    """
    if url_re is None:
        url_re = DEFAULT_URL_RE
    elif url_re:
        if isinstance(url_re, bytes):
            url_re = re.compile(url_re)

    if not delimiters:
        if delimiters is not None:
            return message, []
        delimiters = DEFAULT_DELIMITERS

    delimiters = {k.encode('utf-16le'): v for k, v in delimiters.items()}

    # Cannot use a for loop because we need to skip some indices
    i = 0
    result = []
    current = Mode.NONE

    # Work on byte level with the utf-16le encoding to get the offsets right.
    # The offset will just be half the index we're at.
    message = message.encode('utf-16le')
    while i < len(message):
        url_match = None
        if url_re and current == Mode.NONE:
            # If we're not inside a previous match since Telegram doesn't allow
            # nested message entities, try matching the URL from the i'th pos.
            url_match = url_re.match(message, pos=i)
            if url_match:
                # Replace the whole match with only the inline URL text.
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
                # Slice the string at the current i'th position to see if
                # it matches the current delimiter d.
                if message[i:i + len(d)] == d:
                    if current != Mode.NONE and current != m:
                        # We were inside another delimiter/mode, ignore this.
                        continue

                    if message[i + len(d):i + 2 * len(d)] == d:
                        # The same delimiter can't be right afterwards, if
                        # this were the case we would match empty strings
                        # like `` which we don't want to.
                        continue

                    # Get rid of the delimiter by slicing it away
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

        # Next iteration, utf-16 encoded characters need 2 bytes.
        i += 2

    if result and not isinstance(result[-1], tuple):
        # We may have found some a delimiter but not its ending pair. If
        # that's the case we want to get rid of it before returning.
        # TODO Should probably insert such delimiter back in the string.
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
