"""
Simple markdown parser which does not support nesting. Intended primarily
for use within the library, which attempts to handle emojies correctly,
since they seem to count as two characters and it's a bit strange.
"""
import re

from ..helpers import add_surrogate, del_surrogate, strip_text
from ..tl import TLObject
from ..tl.types import (
    MessageEntityBold, MessageEntityItalic, MessageEntityCode,
    MessageEntityPre, MessageEntityTextUrl, MessageEntityMentionName,
    MessageEntityStrike
)

DEFAULT_DELIMITERS = {
    '**': MessageEntityBold,
    '__': MessageEntityItalic,
    '~~': MessageEntityStrike,
    '`': MessageEntityCode,
    '```': MessageEntityPre
}

DEFAULT_URL_RE = re.compile(r'\[([\S\s]+?)\]\((.+?)\)')
DEFAULT_URL_FORMAT = '[{0}]({1})'


def parse(message, delimiters=None, url_re=None):
    """
    Parses the given markdown message and returns its stripped representation
    plus a list of the MessageEntity's that were found.

    :param message: the message with markdown-like syntax to be parsed.
    :param delimiters: the delimiters to be used, {delimiter: type}.
    :param url_re: the URL bytes regex to be used. Must have two groups.
    :return: a tuple consisting of (clean message, [message entities]).
    """
    if not message:
        return message, []

    if url_re is None:
        url_re = DEFAULT_URL_RE
    elif isinstance(url_re, str):
        url_re = re.compile(url_re)

    if not delimiters:
        if delimiters is not None:
            return message, []
        delimiters = DEFAULT_DELIMITERS

    # Cannot use a for loop because we need to skip some indices
    i = 0
    result = []
    current = None
    end_delimiter = None

    # Work on byte level with the utf-16le encoding to get the offsets right.
    # The offset will just be half the index we're at.
    message = add_surrogate(message)
    while i < len(message):
        if url_re and current is None:
            # If we're not inside a previous match since Telegram doesn't allow
            # nested message entities, try matching the URL from the i'th pos.
            url_match = url_re.match(message, pos=i)
            if url_match:
                # Replace the whole match with only the inline URL text.
                message = ''.join((
                    message[:url_match.start()],
                    url_match.group(1),
                    message[url_match.end():]
                ))

                result.append(MessageEntityTextUrl(
                    offset=url_match.start(), length=len(url_match.group(1)),
                    url=del_surrogate(url_match.group(2))
                ))
                i += len(url_match.group(1))
                # Next loop iteration, don't check delimiters, since
                # a new inline URL might be right after this one.
                continue

        if end_delimiter is None:
            # We're not expecting any delimiter, so check them all
            for d, m in delimiters.items():
                # Slice the string at the current i'th position to see if
                # it matches the current delimiter d, otherwise skip it.
                if message[i:i + len(d)] != d:
                    continue

                if message[i + len(d):i + 2 * len(d)] == d:
                    # The same delimiter can't be right afterwards, if
                    # this were the case we would match empty strings
                    # like `` which we don't want to.
                    continue

                # Get rid of the delimiter by slicing it away
                message = message[:i] + message[i + len(d):]
                if m == MessageEntityPre:
                    # Special case, also has 'lang'
                    current = m(i, None, '')
                else:
                    current = m(i, None)

                end_delimiter = d  # We expect the same delimiter.
                break

        elif message[i:i + len(end_delimiter)] == end_delimiter:
            message = message[:i] + message[i + len(end_delimiter):]
            current.length = i - current.offset
            result.append(current)
            current, end_delimiter = None, None
            # Don't increment i here as we matched a delimiter,
            # and there may be a new one right after. This is
            # different than when encountering the first delimiter,
            # as we already know there won't be the same right after.
            continue

        # Next iteration
        i += 1

    # We may have found some a delimiter but not its ending pair.
    # If this is the case, we want to insert the delimiter character back.
    if current is not None:
        message = (
            message[:current.offset]
            + end_delimiter
            + message[current.offset:]
        )

    message = strip_text(message, result)
    return del_surrogate(message), result


def unparse(text, entities, delimiters=None, url_fmt=None):
    """
    Performs the reverse operation to .parse(), effectively returning
    markdown-like syntax given a normal text and its MessageEntity's.

    :param text: the text to be reconverted into markdown.
    :param entities: the MessageEntity's applied to the text.
    :return: a markdown-like text representing the combination of both inputs.
    """
    if not text or not entities:
        return text

    if not delimiters:
        if delimiters is not None:
            return text
        delimiters = DEFAULT_DELIMITERS

    if url_fmt is None:
        url_fmt = DEFAULT_URL_FORMAT

    if isinstance(entities, TLObject):
        entities = (entities,)
    else:
        entities = tuple(sorted(entities, key=lambda e: e.offset, reverse=True))

    text = add_surrogate(text)
    delimiters = {v: k for k, v in delimiters.items()}
    for entity in entities:
        s = entity.offset
        e = entity.offset + entity.length
        delimiter = delimiters.get(type(entity), None)
        if delimiter:
            text = text[:s] + delimiter + text[s:e] + delimiter + text[e:]
        elif url_fmt:
            url = None
            if isinstance(entity, MessageEntityTextUrl):
                url = entity.url
            elif isinstance(entity, MessageEntityMentionName):
                url = 'tg://user?id={}'.format(entity.user_id)
            if url:
                # It's possible that entities are malformed and end up in the
                # middle of some character, like emoji, by using malformed
                # clients or bots. Try decoding the current one to check if
                # this is the case, and if it is, advance the entity.
                while e <= len(text):
                    try:
                        del_surrogate(text[s:e])
                        break
                    except UnicodeDecodeError:
                        e += 1
                else:
                    # Out of bounds, no luck going forward
                    while e > s:
                        try:
                            del_surrogate(text[s:e])
                            break
                        except UnicodeDecodeError:
                            e -= 1
                    else:
                        # No luck going backwards either, ignore entity
                        continue

                text = (
                    text[:s] +
                    add_surrogate(url_fmt.format(text[s:e], url)) +
                    text[e:]
                )

    return del_surrogate(text)
