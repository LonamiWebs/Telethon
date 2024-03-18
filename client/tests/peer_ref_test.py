import inspect

from pytest import raises
from telethon._impl.session import ChannelRef, GroupRef, PeerRef, UserRef

USER = UserRef(12, 34)
GROUP = GroupRef(5, None)
CHANNEL = ChannelRef(67, 89)


def test_peer_ref() -> None:
    assert PeerRef.from_str(str(USER)) == USER
    assert PeerRef.from_str(str(GROUP)) == GROUP
    assert PeerRef.from_str(str(CHANNEL)) == CHANNEL

    assert inspect.isabstract(PeerRef)

    with raises(ValueError):
        PeerRef.from_str("invalid")


def test_user_ref() -> None:
    assert UserRef.from_str(str(USER)) == USER

    with raises(TypeError):
        UserRef.from_str(str(GROUP))


def test_group_ref() -> None:
    assert GroupRef.from_str(str(GROUP)) == GROUP

    with raises(TypeError):
        GroupRef.from_str(str(CHANNEL))


def test_channel_ref() -> None:
    assert ChannelRef.from_str(str(CHANNEL)) == CHANNEL

    with raises(TypeError):
        ChannelRef.from_str(str(USER))
