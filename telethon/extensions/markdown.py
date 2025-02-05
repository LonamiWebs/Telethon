"""
Simple markdown parser which does not support nesting. Intended primarily
for use within the library, which attempts to handle emojies correctly,
since they seem to count as two characters and it's a bit strange.
"""
import re
import warnings

from ..helpers import add_surrogate, del_surrogate, within_surrogate, strip_text
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

DEFAULT_URL_RE = re.compile(r'\[([\s\S]+?)\]\((.+?)\)')
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

    # Build a regex to efficiently test all delimiters at once.
    # Note that the largest delimiter should go first, we don't
    # want ``` to be interpreted as a single back-tick in a code block.
    delim_re = re.compile('|'.join('({})'.format(re.escape(k))
                                   for k in sorted(delimiters, key=len, reverse=True)))

    # Cannot use a for loop because we need to skip some indices
    i = 0
    result = []

    # Work on byte level with the utf-16le encoding to get the offsets right.
    # The offset will just be half the index we're at.
    message = add_surrogate(message)
    while i < len(message):
        m = delim_re.match(message, pos=i)

        # Did we find some delimiter here at `i`?
        if m:
            delim = next(filter(None, m.groups()))

            # +1 to avoid matching right after (e.g. "****")
            end = message.find(delim, i + len(delim) + 1)

            # Did we find the earliest closing tag?
            if end != -1:

                # Remove the delimiter from the string
                message = ''.join((
                        message[:i],
                        message[i + len(delim):end],
                        message[end + len(delim):]
                ))

                # Check other affected entities
                for ent in result:
                    # If the end is after our start, it is affected
                    if ent.offset + ent.length > i:
                        # If the old start is before ours and the old end is after ours, we are fully enclosed
                        if ent.offset <= i and ent.offset + ent.length >= end + len(delim):
                            ent.length -= len(delim) * 2
                        else:
                            ent.length -= len(delim)

                # Append the found entity
                ent = delimiters[delim]
                if ent == MessageEntityPre:
                    result.append(ent(i, end - i - len(delim), ''))  # has 'lang'
                else:
                    result.append(ent(i, end - i - len(delim)))

                # No nested entities inside code blocks
                if ent in (MessageEntityCode, MessageEntityPre):
                    i = end - len(delim)

                continue

        elif url_re:
            m = url_re.match(message, pos=i)
            if m:
                # Replace the whole match with only the inline URL text.
                message = ''.join((
                    message[:m.start()],
                    m.group(1),
                    message[m.end():]
                ))

                delim_size = m.end() - m.start() - len(m.group(1))
                for ent in result:
                    # If the end is after our start, it is affected
                    if ent.offset + ent.length > m.start():
                        ent.length -= delim_size

                result.append(MessageEntityTextUrl(
                    offset=m.start(), length=len(m.group(1)),
                    url=del_surrogate(m.group(2))
                ))
                i += len(m.group(1))
                continue

        i += 1

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

    if url_fmt is not None:
        warnings.warn('url_fmt is deprecated')  # since it complicates everything *a lot*

    if isinstance(entities, TLObject):
        entities = (entities,)

    text = add_surrogate(text)
    delimiters = {v: k for k, v in delimiters.items()}
    insert_at = []
    for i, entity in enumerate(entities):
        s = entity.offset
        e = entity.offset + entity.length
        delimiter = delimiters.get(type(entity), None)
        if delimiter:
            insert_at.append((s, i, delimiter))
            insert_at.append((e, -i, delimiter))
        else:
            url = None
            if isinstance(entity, MessageEntityTextUrl):
                url = entity.url
            elif isinstance(entity, MessageEntityMentionName):
                url = 'tg://user?id={}'.format(entity.user_id)
            if url:
                insert_at.append((s, i, '['))
                insert_at.append((e, -i, ']({})'.format(url)))

    insert_at.sort(key=lambda t: (t[0], t[1]))
    while insert_at:
        at, _, what = insert_at.pop()

        # If we are in the middle of a surrogate nudge the position by -1.
        # Otherwise we would end up with malformed text and fail to encode.
        # For example of bad input: "Hi \ud83d\ude1c"
        # https://en.wikipedia.org/wiki/UTF-16#U+010000_to_U+10FFFF
        while within_surrogate(text, at):
            at += 1

        text = text[:at] + what + text[at:]

    return del_surrogate(text)
