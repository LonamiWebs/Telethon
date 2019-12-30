"""
Tests for `telethon.crypto.rsa`.
"""
import pytest

from telethon.crypto import rsa


@pytest.fixture
def server_key_fp():
    """Factory to return a key, old if so chosen."""
    def _server_key_fp(old: bool):
        for fp, data in rsa._server_keys.items():
            _, old_key = data
            if old_key == old:
                return fp

    return _server_key_fp


def test_encryption_inv_key():
    """Test for #1324."""
    assert rsa.encrypt("invalid", b"testdata") is None


def test_encryption_old_key(server_key_fp):
    """Test for #1324."""
    assert rsa.encrypt(server_key_fp(old=True), b"testdata") is None


def test_encryption_allowed_old_key(server_key_fp):
    data = rsa.encrypt(server_key_fp(old=True), b"testdata", use_old=True)
    # We can't verify the data is actually valid because we don't have
    # the decryption keys
    assert data is not None and len(data) == 256


def test_encryption_current_key(server_key_fp):
    data = rsa.encrypt(server_key_fp(old=False), b"testdata")
    # We can't verify the data is actually valid because we don't have
    # the decryption keys
    assert data is not None and len(data) == 256
