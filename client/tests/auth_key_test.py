from telethon._impl.crypto import AuthKey


def get_auth_key() -> AuthKey:
    return AuthKey.from_bytes(bytes(range(256)))


def get_new_nonce() -> int:
    return int.from_bytes(bytes(range(32)))


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
    assert auth_key.calc_new_nonce_hash(new_nonce, 1) == 258944117842285651226187582903746985063


def test_calc_new_nonce_hash2() -> None:
    auth_key = get_auth_key()
    new_nonce = get_new_nonce()
    assert auth_key.calc_new_nonce_hash(new_nonce, 2) == 324588944215647649895949797213421233055


def test_calc_new_nonce_hash3() -> None:
    auth_key = get_auth_key()
    new_nonce = get_new_nonce()
    assert auth_key.calc_new_nonce_hash(new_nonce, 3) == 100989356540453064705070297823778556733
