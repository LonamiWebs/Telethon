from telethon._impl.client.parsers import (
    generate_html_message,
    generate_markdown_message,
    parse_html_message,
    parse_markdown_message,
)
from telethon._impl.tl import types


def test_parse_leading_markdown() -> None:
    markdown = "**Hello** world!"
    text, entities = parse_markdown_message(markdown)
    assert text == "Hello world!"
    assert entities == [types.MessageEntityBold(offset=0, length=5)]


def test_parse_trailing_markdown() -> None:
    markdown = "Hello **world!**"
    text, entities = parse_markdown_message(markdown)
    assert text == "Hello world!"
    assert entities == [types.MessageEntityBold(offset=6, length=6)]


def test_parse_emoji_markdown() -> None:
    markdown = "A **little 🦀** here"
    text, entities = parse_markdown_message(markdown)
    assert text == "A little 🦀 here"
    assert entities == [types.MessageEntityBold(offset=2, length=9)]


def test_parse_all_entities_markdown() -> None:
    markdown = "Some **bold** (__strong__), *italics* (_cursive_), inline `code`, a\n```rust\npre\n```\nblock, a [link](https://example.com), and [mentions](tg://user?id=12345678)"
    text, entities = parse_markdown_message(markdown)

    assert (
        text
        == "Some bold (strong), italics (cursive), inline code, a\npre\nblock, a link, and mentions"
    )
    assert entities == [
        types.MessageEntityBold(offset=5, length=4),
        types.MessageEntityBold(offset=11, length=6),
        types.MessageEntityItalic(offset=20, length=7),
        types.MessageEntityItalic(offset=29, length=7),
        types.MessageEntityCode(offset=46, length=4),
        types.MessageEntityPre(offset=54, length=4, language="rust"),
        types.MessageEntityTextUrl(offset=67, length=4, url="https://example.com"),
        types.MessageEntityTextUrl(offset=77, length=8, url="tg://user?id=12345678"),
    ]


def test_parse_nested_entities_markdown() -> None:
    # CommonMark won't allow the following="Some **bold _both** italics_"
    markdown = "Some **bold _both_** _italics_"
    text, entities = parse_markdown_message(markdown)
    assert text == "Some bold both italics"
    assert entities == [
        types.MessageEntityBold(offset=5, length=9),
        types.MessageEntityItalic(offset=10, length=4),
        types.MessageEntityItalic(offset=15, length=7),
    ]


def test_parse_then_unparse_markdown() -> None:
    markdown = "Some **bold 🤷🏽‍♀️**, _italics_, inline `🤷🏽‍♀️ code`, a\n\n```rust\npre\n```\nblock, a [link](https://example.com), and [mentions](tg://user?id=12345678)"
    text, entities = parse_markdown_message(markdown)
    generated = generate_markdown_message(text, entities)
    assert generated == markdown


def test_parse_leading_html() -> None:
    # Intentionally use different casing to make sure that is handled well
    html = "<B>Hello</b> world!"
    text, entities = parse_html_message(html)
    assert text == "Hello world!"
    assert entities == [types.MessageEntityBold(offset=0, length=5)]


def test_parse_trailing_html() -> None:
    html = "Hello <strong>world!</strong>"
    text, entities = parse_html_message(html)
    assert text == "Hello world!"
    assert entities == [types.MessageEntityBold(offset=6, length=6)]


def test_parse_emoji_html() -> None:
    html = "A <b>little 🦀</b> here"
    text, entities = parse_html_message(html)
    assert text == "A little 🦀 here"
    assert entities == [types.MessageEntityBold(offset=2, length=9)]


def test_parse_all_entities_html() -> None:
    html = 'Some <b>bold</b> (<strong>strong</strong>), <i>italics</i> (<em>cursive</em>), inline <code>code</code>, a <pre>pre</pre> block, a <a href="https://example.com">link</a>, <details>spoilers</details> and <a href="tg://user?id=12345678">mentions</a>'
    text, entities = parse_html_message(html)
    assert (
        text
        == "Some bold (strong), italics (cursive), inline code, a pre block, a link, spoilers and mentions"
    )
    assert entities == [
        types.MessageEntityBold(offset=5, length=4),
        types.MessageEntityBold(offset=11, length=6),
        types.MessageEntityItalic(offset=20, length=7),
        types.MessageEntityItalic(offset=29, length=7),
        types.MessageEntityCode(offset=46, length=4),
        types.MessageEntityPre(offset=54, length=3, language=""),
        types.MessageEntityTextUrl(offset=67, length=4, url="https://example.com"),
        types.MessageEntitySpoiler(offset=73, length=8),
        types.MessageEntityTextUrl(offset=86, length=8, url="tg://user?id=12345678"),
    ]


def test_parse_pre_with_lang_html() -> None:
    html = 'Some <pre>pre</pre>, <code>normal</code> and <pre><code class="language-rust">rusty</code></pre> code'
    text, entities = parse_html_message(html)
    assert text == "Some pre, normal and rusty code"
    assert entities == [
        types.MessageEntityPre(offset=5, length=3, language=""),
        types.MessageEntityCode(offset=10, length=6),
        types.MessageEntityPre(offset=21, length=5, language="rust"),
    ]


def test_parse_empty_pre_and_lang_html() -> None:
    html = 'Some empty <pre></pre> and <code class="language-rust">code</code>'
    text, entities = parse_html_message(html)
    assert text == "Some empty  and code"
    assert entities == [types.MessageEntityCode(offset=16, length=4)]


def test_parse_link_no_href_html() -> None:
    html = "Some <a>empty link</a>, it does nothing"
    text, entities = parse_html_message(html)
    assert text == "Some empty link, it does nothing"
    assert entities == []


def test_parse_nested_entities_html() -> None:
    html = "Some <b>bold <i>both</b> italics</i>"
    text, entities = parse_html_message(html)
    assert text == "Some bold both italics"
    assert entities == [
        types.MessageEntityBold(offset=5, length=9),
        types.MessageEntityItalic(offset=10, length=12),
    ]


def test_parse_then_unparse_html() -> None:
    html = 'Some <strong>bold</strong>, <em>italics</em> inline <code>code</code>, a <pre>pre</pre> block <pre><code class="language-rs">use rust;</code></pre>, a <a href="https://example.com">link</a>, <details>spoilers</details> and <a href="tg://user?id=12345678">mentions</a>'
    text, entities = parse_html_message(html)
    generated = generate_html_message(text, entities)
    assert generated == html
