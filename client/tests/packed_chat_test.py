from telethon._impl.session import PackedChat, PackedType


def test_hash_optional() -> None:
    for ty in PackedType:
        pc = PackedChat(ty, 123, 456789)
        assert PackedChat.from_bytes(bytes(pc)) == pc

        pc = PackedChat(ty, 987, None)
        assert PackedChat.from_bytes(bytes(pc)) == pc
