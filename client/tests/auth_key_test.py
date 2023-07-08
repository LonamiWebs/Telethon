from telethon._impl.crypto.auth_key import AuthKey


def get_auth_key() -> AuthKey:
    return AuthKey.from_bytes(bytes(range(256)))


def get_new_nonce() -> bytes:
    return bytes(range(32))


def test_auth_key_aux_hash() -> None:
    auth_key = get_auth_key()
    expected = b"I\x16\xd6\xbd\xb7\xf7\x8eh"

    assert auth_key.aux_hash == expected


def test_auth_key_id() -> None:
    auth_key = get_auth_key()
    expected = b"2\xd1Xn\xa4W\xdf\xc8"

    assert auth_key.key_id == expected


def test_calc_new_nonce_hash1() -> None:
    auth_key = get_auth_key()
    new_nonce = get_new_nonce()
    assert (
        auth_key.calc_new_nonce_hash(new_nonce, 1)
        == b"\xc2\xce\xd2\xb3>Y:U\xd2\x7fJ]\xab\xee|g"
    )


def test_calc_new_nonce_hash2() -> None:
    auth_key = get_auth_key()
    new_nonce = get_new_nonce()
    assert (
        auth_key.calc_new_nonce_hash(new_nonce, 2)
        == b"\xf41\x8e\x85\xbd/\xf3\xbe\x84\xd9\xfe\xfc\xe3\xdc\xe3\x9f"
    )


def test_calc_new_nonce_hash3() -> None:
    auth_key = get_auth_key()
    new_nonce = get_new_nonce()
    assert (
        auth_key.calc_new_nonce_hash(new_nonce, 3)
        == b"K\xf9\xd7\xb3}\xb4\x13\xeeC\x1d(Qv1\xcb="
    )
