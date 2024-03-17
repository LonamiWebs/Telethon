from telethon._impl.session import PackedType, PeerRef


def test_hash_optional() -> None:
    for ty in PackedType:
        pc = PeerRef(ty, 123, 456789)
        assert PeerRef.from_bytes(bytes(pc)) == pc

        pc = PeerRef(ty, 987, None)
        assert PeerRef.from_bytes(bytes(pc)) == pc
