import pytest

from telethon.tl import types, functions


def test_nested_invalid_serialization():
    large_long = 2**62
    request = functions.account.SetPrivacyRequest(
        key=types.InputPrivacyKeyChatInvite(),
        rules=[types.InputPrivacyValueDisallowUsers(users=[large_long])]
    )
    with pytest.raises(TypeError):
        bytes(request)
