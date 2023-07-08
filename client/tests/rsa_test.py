from telethon._impl.crypto.rsa import (
    PRODUCTION_RSA_KEY,
    TESTMODE_RSA_KEY,
    compute_fingerprint,
)


def test_fingerprint_1() -> None:
    fp = compute_fingerprint(PRODUCTION_RSA_KEY)
    assert fp == -3414540481677951611


def test_fingerprint_2() -> None:
    fp = compute_fingerprint(TESTMODE_RSA_KEY)
    assert fp == -5595554452916591101
