"""
Tests for `telethon.extensions.markdown`.
"""
from telethon.extensions import markdown
from telethon.tl.types import MessageEntityBold, MessageEntityItalic, MessageEntityTextUrl


def test_entity_edges():
    """
    Test that entities at the edges (start and end) don't crash.
    """
    text = 'Hello, world'
    entities = [MessageEntityBold(0, 5), MessageEntityBold(7, 5)]
    result = markdown.unparse(text, entities)
    assert result == '**Hello**, **world**'


def test_malformed_entities():
    """
    Test that malformed entity offsets from bad clients
    don't crash and produce the expected results.
    """
    text = '🏆Telegram Official Android Challenge is over🏆.'
    entities = [MessageEntityTextUrl(offset=2, length=43, url='https://example.com')]
    result = markdown.unparse(text, entities)
    assert result == "🏆[Telegram Official Android Challenge is over](https://example.com)🏆."


def test_trailing_malformed_entities():
    """
    Similar to `test_malformed_entities`, but for the edge
    case where the malformed entity offset is right at the end
    (note the lack of a trailing dot in the text string).
    """
    text = '🏆Telegram Official Android Challenge is over🏆'
    entities = [MessageEntityTextUrl(offset=2, length=43, url='https://example.com')]
    result = markdown.unparse(text, entities)
    assert result == "🏆[Telegram Official Android Challenge is over](https://example.com)🏆"


def test_entities_together():
    """
    Test that an entity followed immediately by a different one behaves well.
    """
    original = '**⚙️**__Settings__'
    stripped = '⚙️Settings'

    text, entities = markdown.parse(original)
    assert text == stripped
    assert entities == [MessageEntityBold(0, 2), MessageEntityItalic(2, 8)]

    text = markdown.unparse(text, entities)
    assert text == original


def test_offset_at_emoji():
    """
    Tests that an entity starting at a emoji preserves the emoji.
    """
    text = 'Hi\n👉 See example'
    entities = [MessageEntityBold(0, 2), MessageEntityItalic(3, 2), MessageEntityBold(10, 7)]
    parsed = '**Hi**\n__👉__ See **example**'

    assert markdown.parse(parsed) == (text, entities)
    assert markdown.unparse(text, entities) == parsed
