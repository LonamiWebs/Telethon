import os
import struct
import time
from dataclasses import dataclass
from hashlib import sha1
from typing import Tuple

from ..crypto import (
    RSA_KEYS,
    AuthKey,
    decrypt_ige,
    encrypt_hashed,
    encrypt_ige,
    factorize,
    generate_key_data_from_nonce,
)
from ..tl.core import Reader
from ..tl.mtproto.abcs import ServerDhInnerData as AbcServerDhInnerData
from ..tl.mtproto.abcs import ServerDhParams, SetClientDhParamsAnswer
from ..tl.mtproto.functions import req_dh_params, req_pq_multi, set_client_dh_params
from ..tl.mtproto.types import (
    ClientDhInnerData,
    DhGenFail,
    DhGenOk,
    DhGenRetry,
    PQInnerData,
    ResPq,
    ServerDhInnerData,
    ServerDhParamsFail,
    ServerDhParamsOk,
)


@dataclass
class Step1:
    nonce: int


@dataclass
class Step2:
    nonce: int
    server_nonce: int
    new_nonce: int


@dataclass
class Step3:
    nonce: int
    server_nonce: int
    new_nonce: int
    gab: int
    time_offset: int


@dataclass
class CreatedKey:
    auth_key: AuthKey
    time_offset: int
    first_salt: int


@dataclass
class DhGenData:
    nonce: int
    server_nonce: int
    new_nonce_hash: int
    nonce_number: int


def _do_step1(random_bytes: bytes) -> Tuple[bytes, Step1]:
    assert len(random_bytes) == 16
    nonce = int.from_bytes(random_bytes)
    return req_pq_multi(nonce=nonce), Step1(nonce=nonce)


def step1() -> Tuple[bytes, Step1]:
    return _do_step1(os.urandom(16))


def _do_step2(data: Step1, response: bytes, random_bytes: bytes) -> Tuple[bytes, Step2]:
    assert len(random_bytes) == 288
    nonce = data.nonce
    res_pq = ResPq.from_bytes(response)

    check_nonce(res_pq.nonce, nonce)

    if len(res_pq.pq) != 8:
        raise ValueError(f"invalid pq size: {len(res_pq.pq)}")

    pq = struct.unpack(">Q", res_pq.pq)[0]
    p, q = factorize(pq)

    new_nonce = int.from_bytes(random_bytes[:32])
    random_bytes = random_bytes[32:]

    # https://core.telegram.org/mtproto/auth_key#dh-exchange-initiation
    p_bytes = p.to_bytes((p.bit_length() + 7) // 8)
    q_bytes = q.to_bytes((q.bit_length() + 7) // 8)

    pq_inner_data = bytes(
        PQInnerData(
            pq=res_pq.pq,
            p=p_bytes,
            q=q_bytes,
            nonce=nonce,
            server_nonce=res_pq.server_nonce,
            new_nonce=new_nonce,
        )
    )

    try:
        fingerprint = next(
            fp for fp in res_pq.server_public_key_fingerprints if fp in RSA_KEYS
        )
    except StopIteration:
        raise ValueError(
            f"unknown fingerprints: {res_pq.server_public_key_fingerprints}"
        )

    key = RSA_KEYS[fingerprint]
    ciphertext = encrypt_hashed(pq_inner_data, key, random_bytes)

    return req_dh_params(
        nonce=nonce,
        server_nonce=res_pq.server_nonce,
        p=p_bytes,
        q=q_bytes,
        public_key_fingerprint=fingerprint,
        encrypted_data=ciphertext,
    ), Step2(nonce=nonce, server_nonce=res_pq.server_nonce, new_nonce=new_nonce)


def step2(data: Step1, response: bytes) -> Tuple[bytes, Step2]:
    return _do_step2(data, response, os.urandom(288))


def _do_step3(
    data: Step2, response: bytes, random_bytes: bytes, now: int
) -> Tuple[bytes, Step3]:
    assert len(random_bytes) == 272

    nonce = data.nonce
    server_nonce = data.server_nonce
    new_nonce = data.new_nonce

    server_dh_params = ServerDhParams.from_bytes(response)
    if isinstance(server_dh_params, ServerDhParamsFail):
        check_nonce(server_dh_params.nonce, nonce)
        check_server_nonce(server_dh_params.server_nonce, server_nonce)

        new_nonce_hash = int.from_bytes(sha1(new_nonce.to_bytes(16)).digest()[4:])
        check_new_nonce_hash(server_dh_params.new_nonce_hash, new_nonce_hash)

        raise ValueError("server failed to provide dh params")
    else:
        assert isinstance(server_dh_params, ServerDhParamsOk)

    check_nonce(server_dh_params.nonce, nonce)
    check_server_nonce(server_dh_params.server_nonce, server_nonce)

    if len(server_dh_params.encrypted_answer) % 16 != 0:
        raise ValueError(
            f"encrypted response not padded with size: {len(server_dh_params.encrypted_answer)}"
        )

    key, iv = generate_key_data_from_nonce(server_nonce, new_nonce)
    plain_text_answer = decrypt_ige(server_dh_params.encrypted_answer, key, iv)

    got_answer_hash = plain_text_answer[:20]
    plain_text_reader = Reader(plain_text_answer[20:])

    server_dh_inner = AbcServerDhInnerData._read_from(plain_text_reader)
    assert isinstance(server_dh_inner, ServerDhInnerData)

    expected_answer_hash = sha1(
        plain_text_answer[20 : 20 + plain_text_reader._pos]
    ).digest()

    if got_answer_hash != expected_answer_hash:
        raise ValueError("invalid answer hash")

    check_nonce(server_dh_inner.nonce, nonce)
    check_server_nonce(server_dh_inner.server_nonce, server_nonce)

    dh_prime = int.from_bytes(server_dh_inner.dh_prime)
    g = server_dh_inner.g
    g_a = int.from_bytes(server_dh_inner.g_a)

    time_offset = server_dh_inner.server_time - now

    b = int.from_bytes(random_bytes[:256])
    g_b = pow(g, b, dh_prime)
    gab = pow(g_a, b, dh_prime)

    random_bytes = random_bytes[256:]

    # https://core.telegram.org/mtproto/auth_key#dh-key-exchange-complete
    check_g_in_range(g, 1, dh_prime - 1)
    check_g_in_range(g_a, 1, dh_prime - 1)
    check_g_in_range(g_b, 1, dh_prime - 1)

    safety_range = 1 << (2048 - 64)
    check_g_in_range(g_a, safety_range, dh_prime - safety_range)
    check_g_in_range(g_b, safety_range, dh_prime - safety_range)

    client_dh_inner = bytes(
        ClientDhInnerData(
            nonce=nonce,
            server_nonce=server_nonce,
            retry_id=0,  # TODO use an actual retry_id
            g_b=g_b.to_bytes((g_b.bit_length() + 7) // 8),
        )
    )

    client_dh_inner_hashed = sha1(client_dh_inner).digest() + client_dh_inner
    client_dh_inner_hashed += random_bytes[
        : (16 - (len(client_dh_inner_hashed) % 16)) % 16
    ]

    client_dh_encrypted = encrypt_ige(client_dh_inner_hashed, key, iv)

    return set_client_dh_params(
        nonce=nonce, server_nonce=server_nonce, encrypted_data=client_dh_encrypted
    ), Step3(
        nonce=nonce,
        server_nonce=server_nonce,
        new_nonce=new_nonce,
        gab=gab,
        time_offset=time_offset,
    )


def step3(data: Step2, response: bytes) -> Tuple[bytes, Step3]:
    return _do_step3(data, response, os.urandom(272), int(time.time()))


def create_key(data: Step3, response: bytes) -> CreatedKey:
    nonce = data.nonce
    server_nonce = data.server_nonce
    new_nonce = data.new_nonce
    gab = data.gab
    time_offset = data.time_offset

    dh_gen_answer = SetClientDhParamsAnswer.from_bytes(response)

    if isinstance(dh_gen_answer, DhGenOk):
        dh_gen = DhGenData(
            nonce=dh_gen_answer.nonce,
            server_nonce=dh_gen_answer.server_nonce,
            new_nonce_hash=dh_gen_answer.new_nonce_hash1,
            nonce_number=1,
        )
    elif isinstance(dh_gen_answer, DhGenRetry):
        dh_gen = DhGenData(
            nonce=dh_gen_answer.nonce,
            server_nonce=dh_gen_answer.server_nonce,
            new_nonce_hash=dh_gen_answer.new_nonce_hash2,
            nonce_number=2,
        )
    elif isinstance(dh_gen_answer, DhGenFail):
        dh_gen = DhGenData(
            nonce=dh_gen_answer.nonce,
            server_nonce=dh_gen_answer.server_nonce,
            new_nonce_hash=dh_gen_answer.new_nonce_hash3,
            nonce_number=3,
        )
    else:
        raise ValueError(f"unknown dh gen answer type: {dh_gen_answer}")

    check_nonce(dh_gen.nonce, nonce)
    check_server_nonce(dh_gen.server_nonce, server_nonce)

    auth_key = AuthKey.from_bytes(gab.to_bytes(256))

    new_nonce_hash = auth_key.calc_new_nonce_hash(new_nonce, dh_gen.nonce_number)
    check_new_nonce_hash(dh_gen.new_nonce_hash, new_nonce_hash)

    first_salt = struct.unpack(
        "<q",
        bytes(
            a ^ b
            for a, b in zip(new_nonce.to_bytes(32)[:8], server_nonce.to_bytes(16)[:8])
        ),
    )[0]

    if dh_gen.nonce_number == 1:
        return CreatedKey(
            auth_key=auth_key,
            time_offset=time_offset,
            first_salt=first_salt,
        )
    else:
        raise ValueError("dh gen fail")


def check_nonce(got: int, expected: int) -> None:
    if got != expected:
        raise ValueError(f"invalid nonce, expected: {expected}, got: {got}")


def check_server_nonce(got: int, expected: int) -> None:
    if got != expected:
        raise ValueError(f"invalid server nonce, expected: {expected}, got: {got}")


def check_new_nonce_hash(got: int, expected: int) -> None:
    if got != expected:
        raise ValueError(f"invalid new nonce, expected: {expected}, got: {got}")


def check_g_in_range(value: int, low: int, high: int) -> None:
    if not (low < value < high):
        raise ValueError(f"g parameter {value} not in range({low+1}, {high})")
