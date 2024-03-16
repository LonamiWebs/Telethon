import re
from typing import Any, Dict, Iterator, List, Tuple, Type

import markdown_it
import markdown_it.token

from ...tl.abcs import MessageEntity
from ...tl.types import (
    MessageEntityBlockquote,
    MessageEntityBold,
    MessageEntityCode,
    MessageEntityItalic,
    MessageEntityMentionName,
    MessageEntityPre,
    MessageEntityStrike,
    MessageEntityTextUrl,
    MessageEntityUnderline,
)
from .strings import add_surrogate, del_surrogate, within_surrogate

MARKDOWN = markdown_it.MarkdownIt().enable("strikethrough")
DELIMITERS: Dict[Type[MessageEntity], Tuple[str, str]] = {
    MessageEntityBlockquote: ("> ", ""),
    MessageEntityBold: ("**", "**"),
    MessageEntityCode: ("`", "`"),
    MessageEntityItalic: ("_", "_"),
    MessageEntityStrike: ("~~", "~~"),
    MessageEntityUnderline: ("# ", ""),
}

# Not trying to be complete; just enough to have an alternative (mostly for inline underline).
# The fact headings are treated as underline is an implementation detail.
TAG_PATTERN = re.compile(r"<\s*(/?)\s*(\w+)")
HTML_TO_TYPE = {
    "i": ("em_close", "em_open"),
    "em": ("em_close", "em_open"),
    "b": ("strong_close", "strong_open"),
    "strong": ("strong_close", "strong_open"),
    "s": ("s_close", "s_open"),
    "del": ("s_close", "s_open"),
    "u": ("heading_open", "heading_close"),
    "mark": ("heading_open", "heading_close"),
}


def expand_inline_and_html(
    tokens: List[markdown_it.token.Token],
) -> Iterator[markdown_it.token.Token]:
    for token in tokens:
        if token.type == "inline":
            if token.children:
                yield from expand_inline_and_html(token.children)
        elif token.type == "html_inline":
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


def parse(message: str) -> Tuple[str, List[MessageEntity]]:
    """
    Parses the given markdown message and returns its stripped representation
    plus a list of the MessageEntity's that were found.
    """
    if not message:
        return message, []

    entities: List[MessageEntity]
    token: markdown_it.token.Token

    def push(ty: Any, **extra: object) -> None:
        nonlocal message, entities, token
        if token.nesting > 0:
            entities.append(ty(offset=len(message), length=0, **extra))
        else:
            for entity in reversed(entities):
                if isinstance(entity, ty):
                    setattr(
                        entity, "length", len(message) - getattr(entity, "offset", 0)
                    )
                    break

    parsed = MARKDOWN.parse(add_surrogate(message.strip()))
    message = ""
    entities = []
    last_map = [0, 0]
    for token in expand_inline_and_html(parsed):
        if token.map is not None and token.map != last_map:
            # paragraphs, quotes fences have a line mapping. Use it to determine how many newlines to insert.
            # But don't inssert any (leading) new lines if we're yet to reach the first textual content, or
            # if the mappings are the same (e.g. a quote then opens a paragraph but the mapping is equal).
            if message:
                message += "\n" + "\n" * (token.map[0] - last_map[-1])
            last_map = token.map

        if token.type in ("blockquote_close", "blockquote_open"):
            push(MessageEntityBlockquote)
        elif token.type == "code_block":
            entities.append(
                MessageEntityPre(
                    offset=len(message), length=len(token.content), language=""
                )
            )
            message += token.content
        elif token.type == "code_inline":
            entities.append(
                MessageEntityCode(offset=len(message), length=len(token.content))
            )
            message += token.content
        elif token.type in ("em_close", "em_open"):
            push(MessageEntityItalic)
        elif token.type == "fence":
            entities.append(
                MessageEntityPre(
                    offset=len(message), length=len(token.content), language=token.info
                )
            )
            message += token.content[:-1]  # remove a single trailing newline
        elif token.type == "hardbreak":
            message += "\n"
        elif token.type in ("heading_close", "heading_open"):
            push(MessageEntityUnderline)
        elif token.type == "hr":
            message += "\u2015\n\n"
        elif token.type in ("link_close", "link_open"):
            if (
                token.markup != "autolink"
            ):  # telegram already picks up on these automatically
                push(MessageEntityTextUrl, url=token.attrs.get("href"))
        elif token.type in ("s_close", "s_open"):
            push(MessageEntityStrike)
        elif token.type == "softbreak":
            message += "\n"
        elif token.type in ("strong_close", "strong_open"):
            push(MessageEntityBold)
        elif token.type == "text":
            message += token.content

    return del_surrogate(message), entities


def unparse(text: str, entities: List[MessageEntity]) -> str:
    """
    Performs the reverse operation to .parse(), effectively returning
    markdown-like syntax given a normal text and its MessageEntity's.

    Because there are many possible ways for markdown to produce a certain
    output, this function cannot invert .parse() perfectly.
    """
    if not text or not entities:
        return text

    text = add_surrogate(text)
    insert_at: List[Tuple[int, str]] = []
    for e in entities:
        offset, length = getattr(e, "offset", None), getattr(e, "length", None)
        assert isinstance(offset, int) and isinstance(length, int)

        h = offset
        t = offset + length
        delimiter = DELIMITERS.get(type(e), None)
        if delimiter:
            insert_at.append((h, delimiter[0]))
            insert_at.append((t, delimiter[1]))
        elif isinstance(e, MessageEntityPre):
            insert_at.append((h, f"```{e.language}\n"))
            insert_at.append((t, "```\n"))
        elif isinstance(e, MessageEntityTextUrl):
            insert_at.append((h, "["))
            insert_at.append((t, f"]({e.url})"))
        elif isinstance(e, MessageEntityMentionName):
            insert_at.append((h, "["))
            insert_at.append((t, f"](tg://user?id={e.user_id})"))

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
