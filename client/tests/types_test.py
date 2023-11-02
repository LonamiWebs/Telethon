from pytest import mark
from telethon._impl.client.types import AdminRight
from telethon._impl.tl import types


@mark.parametrize("slot", types.ChatAdminRights.__slots__)
def test_admin_right_covers_all(slot: str) -> None:
    kwargs = {slot: False for slot in types.ChatAdminRights.__slots__}
    kwargs[slot] = True

    rights = types.ChatAdminRights(**kwargs)
    rights_set = AdminRight._from_raw(rights)
    assert len(rights_set) == 1
    assert next(iter(rights_set)).value == slot
