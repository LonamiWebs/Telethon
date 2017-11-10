"""
Simple markdown parser which does not support nesting. Intended primarily
for use within the library, which attempts to handle emojies correctly,
since they seem to count as two characters and it's a bit strange.
"""
import re
from ..tl.types import (
    MessageEntityBold, MessageEntityItalic, MessageEntityCode,
    MessageEntityPre, MessageEntityTextUrl
)


DEFAULT_DELIMITERS = {
    '**': MessageEntityBold,
    '__': MessageEntityItalic,
    '`': MessageEntityCode,
    '```': MessageEntityPre
}

# Regex used to match utf-16le encoded r'\[(.+?)\]\((.+?)\)',
# reason why there's '\0' after every match-literal character.
DEFAULT_URL_RE = re.compile(b'\\[\0(.+?)\\]\0\\(\0(.+?)\\)\0')


def parse(message, delimiters=None, url_re=None):
    """
    Parses the given message and returns the stripped message and a list
    of MessageEntity* using the specified delimiters dictionary (or default
    if None). The dictionary should be a mapping {delimiter: entity class}.

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
    current = None

    # Work on byte level with the utf-16le encoding to get the offsets right.
    # The offset will just be half the index we're at.
    message = message.encode('utf-16le')
    while i < len(message):
        url_match = None
        if url_re and current is None:
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

                result.append(MessageEntityTextUrl(
                    offset=i // 2, length=len(url_match.group(1)) // 2,
                    url=url_match.group(2).decode('utf-16le')
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
                    if current is not None and not isinstance(current, m):
                        # We were inside another delimiter/mode, ignore this.
                        continue

                    if message[i + len(d):i + 2 * len(d)] == d:
                        # The same delimiter can't be right afterwards, if
                        # this were the case we would match empty strings
                        # like `` which we don't want to.
                        continue

                    # Get rid of the delimiter by slicing it away
                    message = message[:i] + message[i + len(d):]
                    if current is None:
                        if m == MessageEntityPre:
                            # Special case, also has 'lang'
                            current = MessageEntityPre(i // 2, None, '')
                        else:
                            current = m(i // 2, None)
                        # No need to i -= 2 here because it's been already
                        # checked that next character won't be a delimiter.
                    else:
                        current.length = (i // 2) - current.offset
                        result.append(current)
                        current = None
                        i -= 2  # Delimiter matched and gone, go back 1 char
                    break

        # Next iteration, utf-16 encoded characters need 2 bytes.
        i += 2

    # We may have found some a delimiter but not its ending pair.
    # TODO Should probably insert such delimiter back in the string.

    return message.decode('utf-16le'), result
