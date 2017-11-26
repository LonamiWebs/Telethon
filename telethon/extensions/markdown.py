"""
Simple markdown parser which does not support nesting. Intended primarily
for use within the library, which attempts to handle emojies correctly,
since they seem to count as two characters and it's a bit strange.
"""
import re

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

# Regex used to match utf-16le encoded r'\[(.+?)\]\((.+?)\)',
# reason why there's '\0' after every match-literal character.
DEFAULT_URL_RE = re.compile(b'\\[\0(.+?)\\]\0\\(\0(.+?)\\)\0')

# Reverse operation for DEFAULT_URL_RE. {0} for text, {1} for URL.
DEFAULT_URL_FORMAT = '[{0}]({1})'

# Encoding to be used
ENC = 'utf-16le'


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
    elif url_re:
        if isinstance(url_re, bytes):
            url_re = re.compile(url_re)

    if not delimiters:
        if delimiters is not None:
            return message, []
        delimiters = DEFAULT_DELIMITERS

    delimiters = {k.encode(ENC): v for k, v in delimiters.items()}

    # Cannot use a for loop because we need to skip some indices
    i = 0
    result = []
    current = None
    end_delimiter = None

    # Work on byte level with the utf-16le encoding to get the offsets right.
    # The offset will just be half the index we're at.
    message = message.encode(ENC)
    while i < len(message):
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
                    url=url_match.group(2).decode(ENC)
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
                    current = m(i // 2, None, '')
                else:
                    current = m(i // 2, None)

                end_delimiter = d  # We expect the same delimiter.
                break

        elif message[i:i + len(end_delimiter)] == end_delimiter:
            message = message[:i] + message[i + len(end_delimiter):]
            current.length = (i // 2) - current.offset
            result.append(current)
            current, end_delimiter = None, None
            # Don't increment i here as we matched a delimiter,
            # and there may be a new one right after. This is
            # different than when encountering the first delimiter,
            # as we already know there won't be the same right after.
            continue

        # Next iteration, utf-16 encoded characters need 2 bytes.
        i += 2

    # We may have found some a delimiter but not its ending pair.
    # If this is the case, we want to insert the delimiter character back.
    if current is not None:
        message = (
            message[:2 * current.offset]
            + end_delimiter
            + message[2 * current.offset:]
        )

    return message.decode(ENC), result


def unparse(text, entities, delimiters=None, url_fmt=None):
    """
    Performs the reverse operation to .parse(), effectively returning
    markdown-like syntax given a normal text and its MessageEntity's.

    :param text: the text to be reconverted into markdown.
    :param entities: the MessageEntity's applied to the text.
    :return: a markdown-like text representing the combination of both inputs.
    """
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

    # Reverse the delimiters, and encode them as utf16
    delimiters = {v: k.encode(ENC) for k, v in delimiters.items()}
    text = text.encode(ENC)
    for entity in entities:
        s = entity.offset * 2
        e = (entity.offset + entity.length) * 2
        delimiter = delimiters.get(type(entity), None)
        if delimiter:
            text = text[:s] + delimiter + text[s:e] + delimiter + text[e:]
        elif isinstance(entity, MessageEntityTextUrl) and url_fmt:
            # If byte-strings supported .format(), we, could have converted
            # the str url_fmt to a byte-string with the following regex:
            # re.sub(b'{\0\s*(?:([01])\0)?\s*}\0',rb'{\1}',url_fmt.encode(ENC))
            #
            # This would preserve {}, {0} and {1}.
            # Alternatively (as it's done), we can decode/encode it every time.
            text = (
                text[:s] +
                url_fmt.format(text[s:e].decode(ENC), entity.url).encode(ENC) +
                text[e:]
            )

    return text.decode(ENC)


def get_inner_text(text, entity):
    """
    Gets the inner text that's surrounded by the given entity or entities.
    For instance: text = 'hey!', entity = MessageEntityBold(2, 2) -> 'y!'.

    :param text: the original text.
    :param entity: the entity or entities that must be matched.
    :return: a single result or a list of the text surrounded by the entities.
    """
    if not isinstance(entity, TLObject) and hasattr(entity, '__iter__'):
        multiple = True
    else:
        entity = [entity]
        multiple = False

    text = text.encode(ENC)
    result = []
    for e in entity:
        start = e.offset * 2
        end = (e.offset + e.length) * 2
        result.append(text[start:end].decode(ENC))

    return result if multiple else result[0]
