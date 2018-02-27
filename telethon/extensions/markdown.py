"""
Simple markdown parser which does not support nesting. Intended primarily
for use within the library, which attempts to handle emojies correctly,
since they seem to count as two characters and it's a bit strange.
"""
import re
import struct

from ..tl import TLObject

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

DEFAULT_URL_RE = re.compile(r'\[([^\]]+)\]\((.+?)\)')
DEFAULT_URL_FORMAT = '[{0}]({1})'


def _add_surrogate(text):
    return ''.join(
        # SMP -> Surrogate Pairs (Telegram offsets are calculated with these).
        # See https://en.wikipedia.org/wiki/Plane_(Unicode)#Overview for more.
        ''.join(chr(y) for y in struct.unpack('<HH', x.encode('utf-16le')))
        if (0x10000 <= ord(x) <= 0x10FFFF) else x for x in text
    )


def _del_surrogate(text):
    return text.encode('utf-16', 'surrogatepass').decode('utf-16')


def parse(message, delimiters=None, url_re=None):
    """
    Parses the given markdown message and returns its stripped representation
    plus a list of the MessageEntity's that were found.

    :param message: the message with markdown-like syntax to be parsed.
    :param delimiters: the delimiters to be used, {delimiter: type}.
    :param url_re: the URL bytes regex to be used. Must have two groups.
    :return: a tuple consisting of (clean message, [message entities]).
    """
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
    message = _add_surrogate(message)
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
                    offset=i, length=len(url_match.group(1)),
                    url=_del_surrogate(url_match.group(2))
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

    return _del_surrogate(message), result


def unparse(text, entities, delimiters=None, url_fmt=None):
    """
    Performs the reverse operation to .parse(), effectively returning
    markdown-like syntax given a normal text and its MessageEntity's.

    :param text: the text to be reconverted into markdown.
    :param entities: the MessageEntity's applied to the text.
    :return: a markdown-like text representing the combination of both inputs.
    """
    if not entities:
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

    text = _add_surrogate(text)
    delimiters = {v: k for k, v in delimiters.items()}
    for entity in entities:
        s = entity.offset
        e = entity.offset + entity.length
        delimiter = delimiters.get(type(entity), None)
        if delimiter:
            text = text[:s] + delimiter + text[s:e] + delimiter + text[e:]
        elif isinstance(entity, MessageEntityTextUrl) and url_fmt:
            text = (
                text[:s] +
                _add_surrogate(url_fmt.format(text[s:e], entity.url)) +
                text[e:]
            )

    return _del_surrogate(text)


def get_inner_text(text, entity):
    """
    Gets the inner text that's surrounded by the given entity or entities.
    For instance: text = 'hey!', entity = MessageEntityBold(2, 2) -> 'y!'.

    :param text: the original text.
    :param entity: the entity or entities that must be matched.
    :return: a single result or a list of the text surrounded by the entities.
    """
    if isinstance(entity, TLObject):
        entity = (entity,)
        multiple = True
    else:
        multiple = False

    text = _add_surrogate(text)
    result = []
    for e in entity:
        start = e.offset
        end = e.offset + e.length
        result.append(_del_surrogate(text[start:end]))

    return result if multiple else result[0]
