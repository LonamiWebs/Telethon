"""
Simple HTML -> Telegram entity parser.
"""
import struct
from collections import deque
from html import escape
from html.parser import HTMLParser
from typing import Iterable, Optional, Tuple, List

from .. import helpers
from ..tl.types import (
    MessageEntityBold, MessageEntityItalic, MessageEntityCode,
    MessageEntityPre, MessageEntityEmail, MessageEntityUrl,
    MessageEntityTextUrl, MessageEntityMentionName,
    MessageEntityUnderline, MessageEntityStrike, MessageEntityBlockquote,
    TypeMessageEntity
)


# Helpers from markdown.py
def _add_surrogate(text):
    return ''.join(
        ''.join(chr(y) for y in struct.unpack('<HH', x.encode('utf-16le')))
        if (0x10000 <= ord(x) <= 0x10FFFF) else x for x in text
    )


def _del_surrogate(text):
    return text.encode('utf-16', 'surrogatepass').decode('utf-16')


class HTMLToTelegramParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text = ''
        self.entities = []
        self._building_entities = {}
        self._open_tags = deque()
        self._open_tags_meta = deque()

    def handle_starttag(self, tag, attrs):
        self._open_tags.appendleft(tag)
        self._open_tags_meta.appendleft(None)

        attrs = dict(attrs)
        EntityType = None
        args = {}
        if tag == 'strong' or tag == 'b':
            EntityType = MessageEntityBold
        elif tag == 'em' or tag == 'i':
            EntityType = MessageEntityItalic
        elif tag == 'u':
            EntityType = MessageEntityUnderline
        elif tag == 'del' or tag == 's':
            EntityType = MessageEntityStrike
        elif tag == 'blockquote':
            EntityType = MessageEntityBlockquote
        elif tag == 'code':
            try:
                # If we're in the middle of a <pre> tag, this <code> tag is
                # probably intended for syntax highlighting.
                #
                # Syntax highlighting is set with
                #     <code class='language-...'>codeblock</code>
                # inside <pre> tags
                pre = self._building_entities['pre']
                try:
                    pre.language = attrs['class'][len('language-'):]
                except KeyError:
                    pass
            except KeyError:
                EntityType = MessageEntityCode
        elif tag == 'pre':
            EntityType = MessageEntityPre
            args['language'] = ''
        elif tag == 'a':
            try:
                url = attrs['href']
            except KeyError:
                return
            if url.startswith('mailto:'):
                url = url[len('mailto:'):]
                EntityType = MessageEntityEmail
            else:
                if self.get_starttag_text() == url:
                    EntityType = MessageEntityUrl
                else:
                    EntityType = MessageEntityTextUrl
                    args['url'] = _del_surrogate(url)
                    url = None
            self._open_tags_meta.popleft()
            self._open_tags_meta.appendleft(url)

        if EntityType and tag not in self._building_entities:
            self._building_entities[tag] = EntityType(
                offset=len(self.text),
                # The length will be determined when closing the tag.
                length=0,
                **args)

    def handle_data(self, text):
        previous_tag = self._open_tags[0] if len(self._open_tags) > 0 else ''
        if previous_tag == 'a':
            url = self._open_tags_meta[0]
            if url:
                text = url

        for tag, entity in self._building_entities.items():
            entity.length += len(text)

        self.text += text

    def handle_endtag(self, tag):
        try:
            self._open_tags.popleft()
            self._open_tags_meta.popleft()
        except IndexError:
            pass
        entity = self._building_entities.pop(tag, None)
        if entity:
            self.entities.append(entity)


def parse(html: str) -> Tuple[str, List[TypeMessageEntity]]:
    """
    Parses the given HTML message and returns its stripped representation
    plus a list of the MessageEntity's that were found.

    :param html: the message with HTML to be parsed.
    :return: a tuple consisting of (clean message, [message entities]).
    """
    if not html:
        return html, []

    parser = HTMLToTelegramParser()
    parser.feed(_add_surrogate(html))
    text = helpers.strip_text(parser.text, parser.entities)
    return _del_surrogate(text), parser.entities


def unparse(text: str, entities: Iterable[TypeMessageEntity], _offset: int = 0,
            _length: Optional[int] = None) -> str:
    """
    Performs the reverse operation to .parse(), effectively returning HTML
    given a normal text and its MessageEntity's.

    :param text: the text to be reconverted into HTML.
    :param entities: the MessageEntity's applied to the text.
    :return: a HTML representation of the combination of both inputs.
    """
    if not text:
        return text
    elif not entities:
        return escape(text)

    text = _add_surrogate(text)
    if _length is None:
        _length = len(text)
    html = []
    last_offset = 0
    for i, entity in enumerate(entities):
        if entity.offset >= _offset + _length:
            break
        relative_offset = entity.offset - _offset
        if relative_offset > last_offset:
            html.append(escape(text[last_offset:relative_offset]))
        elif relative_offset < last_offset:
            continue

        skip_entity = False
        length = entity.length

        # If we are in the middle of a surrogate nudge the position by +1.
        # Otherwise we would end up with malformed text and fail to encode.
        # For example of bad input: "Hi \ud83d\ude1c"
        # https://en.wikipedia.org/wiki/UTF-16#U+010000_to_U+10FFFF
        while helpers.within_surrogate(text, relative_offset, length=_length):
            relative_offset += 1

        while helpers.within_surrogate(text, relative_offset + length, length=_length):
            length += 1

        entity_text = unparse(text=text[relative_offset:relative_offset + length],
                              entities=entities[i + 1:],
                              _offset=entity.offset, _length=length)
        entity_type = type(entity)

        if entity_type == MessageEntityBold:
            html.append('<strong>{}</strong>'.format(entity_text))
        elif entity_type == MessageEntityItalic:
            html.append('<em>{}</em>'.format(entity_text))
        elif entity_type == MessageEntityCode:
            html.append('<code>{}</code>'.format(entity_text))
        elif entity_type == MessageEntityUnderline:
            html.append('<u>{}</u>'.format(entity_text))
        elif entity_type == MessageEntityStrike:
            html.append('<del>{}</del>'.format(entity_text))
        elif entity_type == MessageEntityBlockquote:
            html.append('<blockquote>{}</blockquote>'.format(entity_text))
        elif entity_type == MessageEntityPre:
            if entity.language:
                html.append(
                    "<pre>\n"
                    "    <code class='language-{}'>\n"
                    "        {}\n"
                    "    </code>\n"
                    "</pre>".format(entity.language, entity_text))
            else:
                html.append('<pre><code>{}</code></pre>'
                            .format(entity_text))
        elif entity_type == MessageEntityEmail:
            html.append('<a href="mailto:{0}">{0}</a>'.format(entity_text))
        elif entity_type == MessageEntityUrl:
            html.append('<a href="{0}">{0}</a>'.format(entity_text))
        elif entity_type == MessageEntityTextUrl:
            html.append('<a href="{}">{}</a>'
                        .format(escape(entity.url), entity_text))
        elif entity_type == MessageEntityMentionName:
            html.append('<a href="tg://user?id={}">{}</a>'
                        .format(entity.user_id, entity_text))
        else:
            skip_entity = True
        last_offset = relative_offset + (0 if skip_entity else length)

    while helpers.within_surrogate(text, last_offset, length=_length):
        last_offset += 1

    html.append(escape(text[last_offset:]))
    return _del_surrogate(''.join(html))
