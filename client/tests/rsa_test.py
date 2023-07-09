from rsa import PublicKey
from telethon._impl.crypto.rsa import (
    PRODUCTION_RSA_KEY,
    TESTMODE_RSA_KEY,
    compute_fingerprint,
    encrypt_hashed,
)


def test_fingerprint_1() -> None:
    fp = compute_fingerprint(PRODUCTION_RSA_KEY)
    assert fp == -3414540481677951611


def test_fingerprint_2() -> None:
    fp = compute_fingerprint(TESTMODE_RSA_KEY)
    assert fp == -5595554452916591101


def test_rsa_encryption() -> None:
    key = PublicKey(
        n=22081946531037833540524260580660774032207476521197121128740358761486364763467087828766873972338019078976854986531076484772771735399701424566177039926855356719497736439289455286277202113900509554266057302466528985253648318314129246825219640197356165626774276930672688973278712614800066037531599375044750753580126415613086372604312320014358994394131667022861767539879232149461579922316489532682165746762569651763794500923643656753278887871955676253526661694459370047843286685859688756429293184148202379356802488805862746046071921830921840273062124571073336369210703400985851431491295910187179045081526826572515473914151,
        e=65537,
    )
    result = encrypt_hashed(b"Hello!", key, bytes(256))
    assert (
        result
        == b"up-L\x88\xd2\x9bj\xb945Q$\xdd(\xd9\xb6*GU\x88A\xc8\x03\x14P\xf7I\x9b\x1c\x9ck\xd3\x9d'\xc1X\x1cQ4NQ\xc1y#pd\xa7#\xae\x93\x9dZ\xc3P\x14\xfd\x8bO\xe2Ou\xe3\x11\\2\xa1ci\xee+7:a\xec\x94F\xb9+.=\xf0v\x18\xdb\n\x8a\xfd\xa9\x99\xb6p+2\xb5\x81\x9b\xd6\xeaIp\xfb4|\xa8J`\xd0\xc3\x8a\xb7\x0cf\xe5\xed\x01@D\x88\x89\xa3\xb8\x82\xee\xa53\xba\xd0^\xfa E\xed\xa7\x17\x12<AJ\xbf\xde\xd4>\x1e\xb4\x83\xa0Ixn\xf5\x03\x1b\x12\xd5\x1a?\xf7\xec\xb7\xd8\x04\xd4A5\x94_\x98\xf7ZJl\xf1\xa1\xdf7U\x9e0\xbb\xe9*Kyf\xc3O\x078\xe6\xd10Y\x85wm&\xdf\xab|\x0f\xdf\xd7\xec ,\xc7\x8cT\xcf\x82\xac#\x86\xc7\x9d\x0e\x19u\x80\xa4\xfa\x940\n#\x82\xf9\xe1\x16\xfe\x82\xdf\x9b\xd8r\xe5\xb9\xda{Bb#\xbf\x1a\xd8X\x890\xb5\x1e\x16]l\xdd\x02"
    )
