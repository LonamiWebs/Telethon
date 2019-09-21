import hashlib
import os

from .crypto import factorization
from .tl import types


def check_prime_and_good_check(prime: int, g: int):
    good_prime_bits_count = 2048
    if prime < 0 or prime.bit_length() != good_prime_bits_count:
        raise ValueError('bad prime count {}, expected {}'
                         .format(prime.bit_length(), good_prime_bits_count))

    # TODO This is awfully slow
    if factorization.Factorization.factorize(prime)[0] != 1:
        raise ValueError('given "prime" is not prime')

    if g == 2:
        if prime % 8 != 7:
            raise ValueError('bad g {}, mod8 {}'.format(g, prime % 8))
    elif g == 3:
        if prime % 3 != 2:
            raise ValueError('bad g {}, mod3 {}'.format(g, prime % 3))
    elif g == 4:
        pass
    elif g == 5:
        if prime % 5 not in (1, 4):
            raise ValueError('bad g {}, mod5 {}'.format(g, prime % 5))
    elif g == 6:
        if prime % 24 not in (19, 23):
            raise ValueError('bad g {}, mod24 {}'.format(g, prime % 24))
    elif g == 7:
        if prime % 7 not in (3, 5, 6):
            raise ValueError('bad g {}, mod7 {}'.format(g, prime % 7))
    else:
        raise ValueError('bad g {}'.format(g))

    prime_sub1_div2 = (prime - 1) // 2
    if factorization.Factorization.factorize(prime_sub1_div2)[0] != 1:
        raise ValueError('(prime - 1) // 2 is not prime')

    # Else it's good


def check_prime_and_good(prime_bytes: bytes, g: int):
    good_prime = bytes((
        0xC7, 0x1C, 0xAE, 0xB9, 0xC6, 0xB1, 0xC9, 0x04, 0x8E, 0x6C, 0x52, 0x2F, 0x70, 0xF1, 0x3F, 0x73,
        0x98, 0x0D, 0x40, 0x23, 0x8E, 0x3E, 0x21, 0xC1, 0x49, 0x34, 0xD0, 0x37, 0x56, 0x3D, 0x93, 0x0F,
        0x48, 0x19, 0x8A, 0x0A, 0xA7, 0xC1, 0x40, 0x58, 0x22, 0x94, 0x93, 0xD2, 0x25, 0x30, 0xF4, 0xDB,
        0xFA, 0x33, 0x6F, 0x6E, 0x0A, 0xC9, 0x25, 0x13, 0x95, 0x43, 0xAE, 0xD4, 0x4C, 0xCE, 0x7C, 0x37,
        0x20, 0xFD, 0x51, 0xF6, 0x94, 0x58, 0x70, 0x5A, 0xC6, 0x8C, 0xD4, 0xFE, 0x6B, 0x6B, 0x13, 0xAB,
        0xDC, 0x97, 0x46, 0x51, 0x29, 0x69, 0x32, 0x84, 0x54, 0xF1, 0x8F, 0xAF, 0x8C, 0x59, 0x5F, 0x64,
        0x24, 0x77, 0xFE, 0x96, 0xBB, 0x2A, 0x94, 0x1D, 0x5B, 0xCD, 0x1D, 0x4A, 0xC8, 0xCC, 0x49, 0x88,
        0x07, 0x08, 0xFA, 0x9B, 0x37, 0x8E, 0x3C, 0x4F, 0x3A, 0x90, 0x60, 0xBE, 0xE6, 0x7C, 0xF9, 0xA4,
        0xA4, 0xA6, 0x95, 0x81, 0x10, 0x51, 0x90, 0x7E, 0x16, 0x27, 0x53, 0xB5, 0x6B, 0x0F, 0x6B, 0x41,
        0x0D, 0xBA, 0x74, 0xD8, 0xA8, 0x4B, 0x2A, 0x14, 0xB3, 0x14, 0x4E, 0x0E, 0xF1, 0x28, 0x47, 0x54,
        0xFD, 0x17, 0xED, 0x95, 0x0D, 0x59, 0x65, 0xB4, 0xB9, 0xDD, 0x46, 0x58, 0x2D, 0xB1, 0x17, 0x8D,
        0x16, 0x9C, 0x6B, 0xC4, 0x65, 0xB0, 0xD6, 0xFF, 0x9C, 0xA3, 0x92, 0x8F, 0xEF, 0x5B, 0x9A, 0xE4,
        0xE4, 0x18, 0xFC, 0x15, 0xE8, 0x3E, 0xBE, 0xA0, 0xF8, 0x7F, 0xA9, 0xFF, 0x5E, 0xED, 0x70, 0x05,
        0x0D, 0xED, 0x28, 0x49, 0xF4, 0x7B, 0xF9, 0x59, 0xD9, 0x56, 0x85, 0x0C, 0xE9, 0x29, 0x85, 0x1F,
        0x0D, 0x81, 0x15, 0xF6, 0x35, 0xB1, 0x05, 0xEE, 0x2E, 0x4E, 0x15, 0xD0, 0x4B, 0x24, 0x54, 0xBF,
        0x6F, 0x4F, 0xAD, 0xF0, 0x34, 0xB1, 0x04, 0x03, 0x11, 0x9C, 0xD8, 0xE3, 0xB9, 0x2F, 0xCC, 0x5B))

    if good_prime == prime_bytes:
        if g in (3, 4, 5, 7):
            return  # It's good

    check_prime_and_good_check(int.from_bytes(prime_bytes, 'big'), g)


def is_good_large(number: int, p: int) -> bool:
    return number > 0 and p - number > 0


SIZE_FOR_HASH = 256


def num_bytes_for_hash(number: bytes) -> bytes:
    return bytes(SIZE_FOR_HASH - len(number)) + number


def big_num_for_hash(g: int) -> bytes:
    return g.to_bytes(SIZE_FOR_HASH, 'big')


def sha256(*p: bytes) -> bytes:
    hash = hashlib.sha256()
    for q in p:
        hash.update(q)
    return hash.digest()


def is_good_mod_exp_first(modexp, prime) -> bool:
    diff = prime - modexp
    min_diff_bits_count = 2048 - 64
    max_mod_exp_size = 256
    if diff < 0 or \
            diff.bit_length() < min_diff_bits_count or \
            modexp.bit_length() < min_diff_bits_count or \
            (modexp.bit_length() + 7) // 8 > max_mod_exp_size:
        return False
    return True


def xor(a: bytes, b: bytes) -> bytes:
    return bytes(x ^ y for x, y in zip(a, b))


def pbkdf2sha512(password: bytes, salt: bytes, iterations: int):
    return hashlib.pbkdf2_hmac('sha512', password, salt, iterations)


def compute_hash(algo: types.PasswordKdfAlgoSHA256SHA256PBKDF2HMACSHA512iter100000SHA256ModPow,
                 password: str):
    hash1 = sha256(algo.salt1, password.encode('utf-8'), algo.salt1)
    hash2 = sha256(algo.salt2, hash1, algo.salt2)
    hash3 = pbkdf2sha512(hash2, algo.salt1, 100000)
    return sha256(algo.salt2, hash3, algo.salt2)


def compute_digest(algo: types.PasswordKdfAlgoSHA256SHA256PBKDF2HMACSHA512iter100000SHA256ModPow,
                   password: str):
    try:
        check_prime_and_good(algo.p, algo.g)
    except ValueError:
        raise ValueError('bad p/g in password')

    value = pow(algo.g,
                int.from_bytes(compute_hash(algo, password), 'big'),
                int.from_bytes(algo.p, 'big'))

    return big_num_for_hash(value)


# https://github.com/telegramdesktop/tdesktop/blob/18b74b90451a7db2379a9d753c9cbaf8734b4d5d/Telegram/SourceFiles/core/core_cloud_password.cpp
def compute_check(request: types.account.Password, password: str):
    algo = request.current_algo
    if not isinstance(algo, types.PasswordKdfAlgoSHA256SHA256PBKDF2HMACSHA512iter100000SHA256ModPow):
        raise ValueError('unsupported password algorithm {}'
                         .format(algo.__class__.__name__))

    pw_hash = compute_hash(algo, password)

    p = int.from_bytes(algo.p, 'big')
    g = algo.g
    B = int.from_bytes(request.srp_B, 'big')
    try:
        check_prime_and_good(algo.p, g)
    except ValueError:
        raise ValueError('bad p/g in password')

    if not is_good_large(B, p):
        raise ValueError('bad b in check')

    x = int.from_bytes(pw_hash, 'big')
    p_for_hash = num_bytes_for_hash(algo.p)
    g_for_hash = big_num_for_hash(g)
    b_for_hash = num_bytes_for_hash(request.srp_B)
    g_x = pow(g, x, p)
    k = int.from_bytes(sha256(p_for_hash, g_for_hash), 'big')
    kg_x = (k * g_x) % p

    def generate_and_check_random():
        random_size = 256
        import time
        while True:
            random = os.urandom(random_size)
            a = int.from_bytes(random, 'big')
            A = pow(g, a, p)
            if is_good_mod_exp_first(A, p):
                a_for_hash = big_num_for_hash(A)
                u = int.from_bytes(sha256(a_for_hash, b_for_hash), 'big')
                if u > 0:
                    return (a, a_for_hash, u)

    a, a_for_hash, u = generate_and_check_random()
    g_b = (B - kg_x) % p
    if not is_good_mod_exp_first(g_b, p):
        raise ValueError('bad g_b')

    ux = u * x
    a_ux = a + ux
    S = pow(g_b, a_ux, p)
    K = sha256(big_num_for_hash(S))
    M1 = sha256(
        xor(sha256(p_for_hash), sha256(g_for_hash)),
        sha256(algo.salt1),
        sha256(algo.salt2),
        a_for_hash,
        b_for_hash,
        K
    )

    return types.InputCheckPasswordSRP(
        request.srp_id, bytes(a_for_hash), bytes(M1))
