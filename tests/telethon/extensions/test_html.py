"""
Tests for `telethon.extensions.html`.
"""
from telethon.extensions import html
from telethon.tl.types import MessageEntityBold, MessageEntityTextUrl


def test_entity_edges():
    """
    Test that entities at the edges (start and end) don't crash.
    """
    text = 'Hello, world'
    entities = [MessageEntityBold(0, 5), MessageEntityBold(7, 5)]
    result = html.unparse(text, entities)
    assert result == '<strong>Hello</strong>, <strong>world</strong>'


def test_malformed_entities():
    """
    Test that malformed entity offsets from bad clients
    don't crash and produce the expected results.
    """
    text = '🏆Telegram Official Android Challenge is over🏆.'
    entities = [MessageEntityTextUrl(offset=2, length=43, url='https://example.com')]
    result = html.unparse(text, entities)
    assert result == '🏆<a href="https://example.com">Telegram Official Android Challenge is over🏆</a>.'


def test_trailing_malformed_entities():
    """
    Similar to `test_malformed_entities`, but for the edge
    case where the malformed entity offset is right at the end
    (note the lack of a trailing dot in the text string).
    """
    text = '🏆Telegram Official Android Challenge is over🏆'
    entities = [MessageEntityTextUrl(offset=2, length=43, url='https://example.com')]
    result = html.unparse(text, entities)
    assert result == '🏆<a href="https://example.com">Telegram Official Android Challenge is over🏆</a>'
