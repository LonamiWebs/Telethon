"""
tests for telethon.helpers
"""

from base64 import b64decode

import pytest

from telethon import helpers
from telethon.utils import get_inner_text
from telethon.tl.types import MessageEntityUnknown as Meu


def test_strip_text():
    text = ' text '
    text_stripped = 'text'
    entities_before_and_after = (
        ([], []),
        ([Meu(i, 0) for i in range(10)], []),  # del ''
        ([Meu(0, 0), Meu(0, 1), Meu(5, 1)], []),  # del '', ' ', ' '
        ([Meu(0, 3)], [Meu(0, 2)]),  # ' te' -> 'te'
        ([Meu(3, 1)], [Meu(2, 1)]),  # 'x'
        ([Meu(3, 2)], [Meu(2, 2)]),  # 'xt'
        ([Meu(3, 3)], [Meu(2, 2)]),  # 'xt ' -> 'xt'
        ([Meu(0, 6)], [Meu(0, 4)]),  # ' text ' -> 'text'
    )
    for entities_before, entities_expected in entities_before_and_after:
        entities_for_test = [Meu(meu.offset, meu.length) for meu in entities_before]  # deep copy
        text_after = helpers.strip_text(text, entities_for_test)
        assert text_after == text_stripped
        assert sorted((e.offset, e.length) for e in entities_for_test) \
               == sorted((e.offset, e.length) for e in entities_expected)
        inner_text_before = get_inner_text(text, entities_before)
        inner_text_before_stripped = [t.strip() for t in inner_text_before]
        inner_text_after = get_inner_text(text_after, entities_for_test)
        for t in inner_text_after:
            assert t in inner_text_before_stripped


class TestSyncifyAsyncContext:
    class NoopContextManager:
        def __init__(self, loop):
            self.count = 0
            self.loop = loop

        async def __aenter__(self):
            self.count += 1
            return self

        async def __aexit__(self, exc_type, *args):
            assert exc_type is None
            self.count -= 1

        __enter__ = helpers._sync_enter
        __exit__ = helpers._sync_exit

    def test_sync_acontext(self, event_loop):
        contm = self.NoopContextManager(event_loop)
        assert contm.count == 0

        with contm:
            assert contm.count == 1

        assert contm.count == 0

    @pytest.mark.asyncio
    async def test_async_acontext(self, event_loop):
        contm = self.NoopContextManager(event_loop)
        assert contm.count == 0

        async with contm:
            assert contm.count == 1

        assert contm.count == 0


def test_generate_key_data_from_nonce():
    gkdfn = helpers.generate_key_data_from_nonce

    key_expect = b64decode(b'NFwRFB8Knw/kAmvPWjtrQauWysHClVfQh0UOAaABqZA=')
    nonce_expect = b64decode(b'1AgjhU9eDvJRjFik73bjR2zZEATzL/jLu9yodYfWEgA=')
    assert gkdfn(123456789, 1234567) == (key_expect, nonce_expect)
