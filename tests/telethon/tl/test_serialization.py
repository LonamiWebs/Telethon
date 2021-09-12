import pytest

from telethon import _tl


def test_nested_invalid_serialization():
    large_long = 2**62
    request = _tl.fn.account.SetPrivacy(
        key=_tl.InputPrivacyKeyChatInvite(),
        rules=[_tl.InputPrivacyValueDisallowUsers(users=[large_long])]
    )
    with pytest.raises(TypeError):
        bytes(request)
