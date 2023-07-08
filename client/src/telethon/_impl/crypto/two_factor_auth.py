# Ported from https://github.com/Lonami/grammers/blob/d91dc82/lib/grammers-crypto/src/two_factor_auth.rs
from collections import namedtuple
from hashlib import pbkdf2_hmac, sha256

from .factorize import factorize

TwoFactorAuth = namedtuple("TwoFactorAuth", ("m1", "g_a"))


def pad_to_256(data: bytes) -> bytes:
    return bytes(256 - len(data)) + data


# H(data) := sha256(data)
def h(*data: bytes) -> bytes:
    return sha256(b"".join(data)).digest()


# SH(data, salt) := H(salt | data | salt)
def sh(data: bytes, salt: bytes) -> bytes:
    return h(salt, data, salt)


# PH1(password, salt1, salt2) := SH(SH(password, salt1), salt2)
def ph1(password: bytes, salt1: bytes, salt2: bytes) -> bytes:
    return sh(sh(password, salt1), salt2)


# PH2(password, salt1, salt2) := SH(pbkdf2(sha512, PH1(password, salt1, salt2), salt1, 100000), salt2)
def ph2(password: bytes, salt1: bytes, salt2: bytes) -> bytes:
    return sh(pbkdf2_hmac("sha512", ph1(password, salt1, salt2), salt1, 100000), salt2)


# https://core.telegram.org/api/srp
def calculate_2fa(
    *,
    salt1: bytes,
    salt2: bytes,
    g: int,
    p: bytes,
    g_b: bytes,
    a: bytes,
    password: bytes,
) -> TwoFactorAuth:
    big_p = int.from_bytes(p)

    g_b = pad_to_256(g_b)
    a = pad_to_256(a)

    g_for_hash = g.to_bytes(256)

    big_g_b = int.from_bytes(g_b)

    big_g = g
    big_a = int.from_bytes(a)

    # k := H(p | g)
    k = h(p, g_for_hash)
    big_k = int.from_bytes(k)

    # g_a := pow(g, a) mod p
    g_a = pow(big_g, big_a, big_p).to_bytes(256)

    # u := H(g_a | g_b)
    u = int.from_bytes(h(g_a, g_b))

    # x := PH2(password, salt1, salt2)
    x = int.from_bytes(ph2(password, salt1, salt2))

    # v := pow(g, x) mod p
    big_v = pow(big_g, x, big_p)

    # k_v := (k * v) mod p
    k_v = (big_k * big_v) % big_p

    # t := (g_b - k_v) mod p (positive modulo, if the result is negative increment by p)
    if big_g_b > k_v:
        sub = big_g_b - k_v
    else:
        sub = k_v - big_g_b

    big_t = sub % big_p

    # s_a := pow(t, a + u * x) mod p
    first = u * x
    second = big_a + first
    big_s_a = pow(big_t, second, big_p)

    # k_a := H(s_a)
    k_a = h(big_s_a.to_bytes(256))

    # M1 := H(H(p) xor H(g) | H(salt1) | H(salt2) | g_a | g_b | k_a)
    h_p = h(p)
    h_g = h(g_for_hash)

    p_xor_g = bytes(hpi ^ hgi for hpi, hgi in zip(h_p, h_g))

    m1 = h(p_xor_g, h(salt1), h(salt2), g_a, g_b, k_a)

    return TwoFactorAuth(m1, g_a)


def check_p_len(p: bytes) -> bool:
    return len(p) == 256


def check_known_prime(p: bytes, g: int) -> bool:
    good_prime = b"\xc7\x1c\xae\xb9\xc6\xb1\xc9\x04\x8elR/p\xf1?s\x98\r@#\x8e>!\xc1I4\xd07V=\x93\x0fH\x19\x8a\n\xa7\xc1@X\"\x94\x93\xd2%0\xf4\xdb\xfa3on\n\xc9%\x13\x95C\xae\xd4L\xce|7 \xfdQ\xf6\x94XpZ\xc6\x8c\xd4\xfekk\x13\xab\xdc\x97FQ)i2\x84T\xf1\x8f\xaf\x8cY_d$w\xfe\x96\xbb*\x94\x1d[\xcd\x1dJ\xc8\xccI\x88\x07\x08\xfa\x9b7\x8e<O:\x90`\xbe\xe6|\xf9\xa4\xa4\xa6\x95\x81\x10Q\x90~\x16'S\xb5k\x0fkA\r\xbat\xd8\xa8K*\x14\xb3\x14N\x0e\xf1(GT\xfd\x17\xed\x95\rYe\xb4\xb9\xddFX-\xb1\x17\x8d\x16\x9ck\xc4e\xb0\xd6\xff\x9c\xa3\x92\x8f\xef[\x9a\xe4\xe4\x18\xfc\x15\xe8>\xbe\xa0\xf8\x7f\xa9\xff^\xedp\x05\r\xed(I\xf4{\xf9Y\xd9V\x85\x0c\xe9)\x85\x1f\r\x81\x15\xf65\xb1\x05\xee.N\x15\xd0K$T\xbfoO\xad\xf04\xb1\x04\x03\x11\x9c\xd8\xe3\xb9/\xcc["
    return p == good_prime and g in (3, 4, 5, 7)


def check_p_prime_and_subgroup(p: bytes, g: int) -> bool:
    if check_known_prime(p, g):
        return True

    big_p = int.from_bytes(p)

    if g == 2:
        candidate = big_p % 8 == 7
    elif g == 3:
        candidate = big_p % 3 == 2
    elif g == 4:
        candidate = True
    elif g == 5:
        candidate = (big_p % 5) in (1, 4)
    elif g == 6:
        candidate = (big_p % 24) in (19, 23)
    elif g == 7:
        candidate = (big_p % 7) in (3, 5, 6)
    else:
        raise ValueError(f"bad g: {g}")

    return candidate and factorize((big_p - 1) // 2)[0] == 1


def check_p_and_g(p: bytes, g: int) -> bool:
    if not check_p_len(p):
        return False

    return check_p_prime_and_subgroup(p, g)
