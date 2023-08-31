from collections import deque
from html import escape
from html.parser import HTMLParser
from typing import Any, Deque, Dict, Iterable, List, Optional, Tuple, Type, cast

from ...tl.abcs import MessageEntity
from ...tl.types import (
    MessageEntityBlockquote,
    MessageEntityBold,
    MessageEntityCode,
    MessageEntityEmail,
    MessageEntityItalic,
    MessageEntityMentionName,
    MessageEntityPre,
    MessageEntitySpoiler,
    MessageEntityStrike,
    MessageEntityTextUrl,
    MessageEntityUnderline,
    MessageEntityUrl,
)
from .strings import add_surrogate, del_surrogate, strip_text, within_surrogate


class HTMLToTelegramParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.text = ""
        self.entities: List[MessageEntity] = []
        self._building_entities: Dict[str, MessageEntity] = {}
        self._open_tags: Deque[str] = deque()
        self._open_tags_meta: Deque[Optional[str]] = deque()

    def handle_starttag(
        self, tag: str, attrs_seq: List[Tuple[str, Optional[str]]]
    ) -> None:
        self._open_tags.appendleft(tag)
        self._open_tags_meta.appendleft(None)

        attrs = dict(attrs_seq)
        EntityType: Optional[Type[MessageEntity]] = None
        args = {}
        if tag == "strong" or tag == "b":
            EntityType = MessageEntityBold
        elif tag == "em" or tag == "i":
            EntityType = MessageEntityItalic
        elif tag == "u":
            EntityType = MessageEntityUnderline
        elif tag == "del" or tag == "s":
            EntityType = MessageEntityStrike
        elif tag == "blockquote":
            EntityType = MessageEntityBlockquote
        elif tag == "details":
            EntityType = MessageEntitySpoiler
        elif tag == "code":
            try:
                # If we're in the middle of a <pre> tag, this <code> tag is
                # probably intended for syntax highlighting.
                #
                # Syntax highlighting is set with
                #     <code class='language-...'>codeblock</code>
                # inside <pre> tags
                pre = self._building_entities["pre"]
                assert isinstance(pre, MessageEntityPre)
                if cls := attrs.get("class"):
                    pre.language = cls[len("language-") :]
            except KeyError:
                EntityType = MessageEntityCode
        elif tag == "pre":
            EntityType = MessageEntityPre
            args["language"] = ""
        elif tag == "a":
            url = attrs.get("href")
            if not url:
                return
            if url.startswith("mailto:"):
                url = url[len("mailto:") :]
                EntityType = MessageEntityEmail
            else:
                if self.get_starttag_text() == url:
                    EntityType = MessageEntityUrl
                else:
                    EntityType = MessageEntityTextUrl
                    args["url"] = del_surrogate(url)
                    url = None
            self._open_tags_meta.popleft()
            self._open_tags_meta.appendleft(url)

        if EntityType and tag not in self._building_entities:
            Et = cast(Any, EntityType)
            self._building_entities[tag] = Et(
                offset=len(self.text),
                # The length will be determined when closing the tag.
                length=0,
                **args,
            )

    def handle_data(self, text: str) -> None:
        previous_tag = self._open_tags[0] if len(self._open_tags) > 0 else ""
        if previous_tag == "a":
            url = self._open_tags_meta[0]
            if url:
                text = url

        for entity in self._building_entities.values():
            assert hasattr(entity, "length")
            entity.length += len(text)

        self.text += text

    def handle_endtag(self, tag: str) -> None:
        try:
            self._open_tags.popleft()
            self._open_tags_meta.popleft()
        except IndexError:
            pass
        entity = self._building_entities.pop(tag, None)
        if entity and hasattr(entity, "length") and entity.length:
            self.entities.append(entity)


def parse(html: str) -> Tuple[str, List[MessageEntity]]:
    """
    Parses the given HTML message and returns its stripped representation
    plus a list of the MessageEntity's that were found.

    :param html: the message with HTML to be parsed.
    :return: a tuple consisting of (clean message, [message entities]).
    """
    if not html:
        return html, []

    parser = HTMLToTelegramParser()
    parser.feed(add_surrogate(html))
    text = strip_text(parser.text, parser.entities)
    return del_surrogate(text), parser.entities


ENTITY_TO_FORMATTER = {
    MessageEntityBold: ("<strong>", "</strong>"),
    MessageEntityItalic: ("<em>", "</em>"),
    MessageEntityCode: ("<code>", "</code>"),
    MessageEntityUnderline: ("<u>", "</u>"),
    MessageEntityStrike: ("<del>", "</del>"),
    MessageEntityBlockquote: ("<blockquote>", "</blockquote>"),
    MessageEntitySpoiler: ("<details>", "</details>"),
    MessageEntityPre: lambda e, _: (
        '<pre><code class="language-{}">'.format(e.language) if e.language else "<pre>",
        "</code></pre>" if e.language else "</pre>",
    ),
    MessageEntityEmail: lambda _, t: ('<a href="mailto:{}">'.format(t), "</a>"),
    MessageEntityUrl: lambda _, t: ('<a href="{}">'.format(t), "</a>"),
    MessageEntityTextUrl: lambda e, _: ('<a href="{}">'.format(escape(e.url)), "</a>"),
    MessageEntityMentionName: lambda e, _: (
        '<a href="tg://user?id={}">'.format(e.user_id),
        "</a>",
    ),
}


def unparse(text: str, entities: Iterable[MessageEntity]) -> str:
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

    text = add_surrogate(text)
    insert_at: List[Tuple[int, str]] = []
    for entity in entities:
        assert hasattr(entity, "offset") and hasattr(entity, "length")
        s = entity.offset
        e = entity.offset + entity.length
        delimiter = ENTITY_TO_FORMATTER.get(type(entity), None)
        if delimiter:
            if callable(delimiter):
                delim = delimiter(entity, text[s:e])
            else:
                delim = delimiter
            insert_at.append((s, delim[0]))
            insert_at.append((e, delim[1]))

    insert_at.sort(key=lambda t: t[0])
    next_escape_bound = len(text)
    while insert_at:
        # Same logic as markdown.py
        at, what = insert_at.pop()
        while within_surrogate(text, at):
            at += 1

        text = (
            text[:at]
            + what
            + escape(text[at:next_escape_bound])
            + text[next_escape_bound:]
        )
        next_escape_bound = at

    text = escape(text[:next_escape_bound]) + text[next_escape_bound:]

    return del_surrogate(text)
