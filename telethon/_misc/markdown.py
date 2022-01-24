"""
Simple markdown parser which does not support nesting. Intended primarily
for use within the library, which attempts to handle emojies correctly,
since they seem to count as two characters and it's a bit strange.
"""
import re
import warnings
import markdown_it

from .helpers import add_surrogate, del_surrogate, within_surrogate, strip_text
from .. import _tl
from .._misc import tlobject


MARKDOWN = markdown_it.MarkdownIt().enable('strikethrough')
DELIMITERS = {
    _tl.MessageEntityBlockquote: ('> ', ''),
    _tl.MessageEntityBold: ('**', '**'),
    _tl.MessageEntityCode: ('`', '`'),
    _tl.MessageEntityItalic: ('_', '_'),
    _tl.MessageEntityStrike: ('~~', '~~'),
    _tl.MessageEntitySpoiler: ('||', '||'),
    _tl.MessageEntityUnderline: ('# ', ''),
}

# Not trying to be complete; just enough to have an alternative (mostly for inline underline).
# The fact headings are treated as underline is an implementation detail.
TAG_PATTERN = re.compile(r'<\s*(/?)\s*(\w+)')
HTML_TO_TYPE = {
    'i': ('em_close', 'em_open'),
    'em': ('em_close', 'em_open'),
    'b': ('strong_close', 'strong_open'),
    'strong': ('strong_close', 'strong_open'),
    's': ('s_close', 's_open'),
    'del': ('s_close', 's_open'),
    'u': ('heading_open', 'heading_close'),
    'mark': ('heading_open', 'heading_close'),
}


def expand_inline_and_html(tokens):
    for token in tokens:
        if token.type == 'inline':
            yield from expand_inline_and_html(token.children)
        elif token.type == 'html_inline':
            match = TAG_PATTERN.match(token.content)
            if match:
                close, tag = match.groups()
                tys = HTML_TO_TYPE.get(tag.lower())
                if tys:
                    token.type = tys[bool(close)]
                    token.nesting = -1 if close else 1
                    yield token
        else:
            yield token


def parse(message):
    """
    Parses the given markdown message and returns its stripped representation
    plus a list of the _tl.MessageEntity's that were found.
    """
    if not message:
        return message, []

    def push(ty, **extra):
        nonlocal message, entities, token
        if token.nesting > 0:
            entities.append(ty(offset=len(message), length=0, **extra))
        else:
            for entity in reversed(entities):
                if isinstance(entity, ty):
                    entity.length = len(message) - entity.offset
                    break

    parsed = MARKDOWN.parse(add_surrogate(message.strip()))
    message = ''
    entities = []
    last_map = [0, 0]
    for token in expand_inline_and_html(parsed):
        if token.map is not None and token.map != last_map:
            # paragraphs, quotes fences have a line mapping. Use it to determine how many newlines to insert.
            # But don't inssert any (leading) new lines if we're yet to reach the first textual content, or
            # if the mappings are the same (e.g. a quote then opens a paragraph but the mapping is equal).
            if message:
                message += '\n' + '\n' * (token.map[0] - last_map[-1])
            last_map = token.map

        if token.type in ('blockquote_close', 'blockquote_open'):
            push(_tl.MessageEntityBlockquote)
        elif token.type == 'code_block':
            entities.append(_tl.MessageEntityPre(offset=len(message), length=len(token.content), language=''))
            message += token.content
        elif token.type == 'code_inline':
            entities.append(_tl.MessageEntityCode(offset=len(message), length=len(token.content)))
            message += token.content
        elif token.type in ('em_close', 'em_open'):
            push(_tl.MessageEntityItalic)
        elif token.type == 'fence':
            entities.append(_tl.MessageEntityPre(offset=len(message), length=len(token.content), language=token.info))
            message += token.content[:-1]  # remove a single trailing newline
        elif token.type == 'hardbreak':
            message += '\n'
        elif token.type in ('heading_close', 'heading_open'):
            push(_tl.MessageEntityUnderline)
        elif token.type == 'hr':
            message += '\u2015\n\n'
        elif token.type in ('link_close', 'link_open'):
            if token.markup != 'autolink':  # telegram already picks up on these automatically
                push(_tl.MessageEntityTextUrl, url=token.attrs.get('href'))
        elif token.type in ('s_close', 's_open'):
            push(_tl.MessageEntityStrike)
        elif token.type == 'softbreak':
            message += ' '
        elif token.type in ('strong_close', 'strong_open'):
            push(_tl.MessageEntityBold)
        elif token.type == 'text':
            message += token.content

    return del_surrogate(message), entities


def unparse(text, entities):
    """
    Performs the reverse operation to .parse(), effectively returning
    markdown-like syntax given a normal text and its _tl.MessageEntity's.

    Because there are many possible ways for markdown to produce a certain
    output, this function cannot invert .parse() perfectly.
    """
    if not text or not entities:
        return text

    if isinstance(entities, tlobject.TLObject):
        entities = (entities,)

    text = add_surrogate(text)
    insert_at = []
    for entity in entities:
        s = entity.offset
        e = entity.offset + entity.length
        delimiter = DELIMITERS.get(type(entity), None)
        if delimiter:
            insert_at.append((s, delimiter[0]))
            insert_at.append((e, delimiter[1]))
        elif isinstance(entity, _tl.MessageEntityPre):
            insert_at.append((s, f'```{entity.language}\n'))
            insert_at.append((e, '```\n'))
        elif isinstance(entity, _tl.MessageEntityTextUrl):
            insert_at.append((s, '['))
            insert_at.append((e, f']({entity.url})'))
        elif isinstance(entity, _tl.MessageEntityMentionName):
            insert_at.append((s, '['))
            insert_at.append((e, f'](tg://user?id={entity.user_id})'))

    insert_at.sort(key=lambda t: t[0])
    while insert_at:
        at, what = insert_at.pop()

        # If we are in the middle of a surrogate nudge the position by -1.
        # Otherwise we would end up with malformed text and fail to encode.
        # For example of bad input: "Hi \ud83d\ude1c"
        # https://en.wikipedia.org/wiki/UTF-16#U+010000_to_U+10FFFF
        while within_surrogate(text, at):
            at += 1

        text = text[:at] + what + text[at:]

    return del_surrogate(text)
