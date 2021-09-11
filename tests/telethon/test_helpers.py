"""
tests for telethon.helpers
"""

from base64 import b64decode

import pytest

from telethon import helpers


def test_strip_text():
    assert helpers.strip_text(" text ", []) == "text"
    # I can't interpret the rest of the code well enough yet


def test_generate_key_data_from_nonce():
    gkdfn = helpers.generate_key_data_from_nonce

    key_expect = b64decode(b'NFwRFB8Knw/kAmvPWjtrQauWysHClVfQh0UOAaABqZA=')
    nonce_expect = b64decode(b'1AgjhU9eDvJRjFik73bjR2zZEATzL/jLu9yodYfWEgA=')
    assert gkdfn(123456789, 1234567) == (key_expect, nonce_expect)
