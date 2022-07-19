"""
This module contains several functions that authenticate the client machine
with Telegram's servers, effectively creating an authorization key.
"""
import asyncio
import functools
import os
import time
from hashlib import sha1

from .. import _tl
from .._misc import helpers
from .._crypto import AES, AuthKey, Factorization, rsa
from ..errors._custom import SecurityError
from .._misc.binaryreader import BinaryReader


async def do_authentication(sender):
    """
    Executes the authentication process with the Telegram servers.

    :param sender: a connected `MTProtoPlainSender`.
    :return: returns a (authorization key, time offset) tuple.
    """
    # Step 1 sending: PQ Request, endianness doesn't matter since it's random
    nonce = int.from_bytes(os.urandom(16), 'big', signed=True)
    res_pq = await sender.send(_tl.fn.ReqPqMulti(nonce))
    assert isinstance(res_pq, _tl.ResPQ), 'Step 1 answer was %s' % res_pq

    if res_pq.nonce != nonce:
        raise SecurityError('Step 1 invalid nonce from server')

    pq = get_int(res_pq.pq)

    # Step 2 sending: DH Exchange
    p, q = await asyncio.get_running_loop().run_in_executor(
        None,
        functools.partial(Factorization.factorize, pq)
    )
    p, q = rsa.get_byte_array(p), rsa.get_byte_array(q)
    new_nonce = int.from_bytes(os.urandom(32), 'little', signed=True)

    pq_inner_data = bytes(_tl.PQInnerData(
        pq=rsa.get_byte_array(pq), p=p, q=q,
        nonce=res_pq.nonce,
        server_nonce=res_pq.server_nonce,
        new_nonce=new_nonce
    ))

    # sha_digest + data + random_bytes
    cipher_text, target_fingerprint = None, None
    for fingerprint in res_pq.server_public_key_fingerprints:
        cipher_text = rsa.encrypt(fingerprint, pq_inner_data)
        if cipher_text is not None:
            target_fingerprint = fingerprint
            break

    if cipher_text is None:
        # Second attempt, but now we're allowed to use old keys
        for fingerprint in res_pq.server_public_key_fingerprints:
            cipher_text = rsa.encrypt(fingerprint, pq_inner_data, use_old=True)
            if cipher_text is not None:
                target_fingerprint = fingerprint
                break

    if cipher_text is None:
        raise SecurityError(
            'Step 2 could not find a valid key for fingerprints: {}'
            .format(', '.join(
                [str(f) for f in res_pq.server_public_key_fingerprints])
            )
        )

    server_dh_params = await sender.send(_tl.fn.ReqDHParams(
        nonce=res_pq.nonce,
        server_nonce=res_pq.server_nonce,
        p=p, q=q,
        public_key_fingerprint=target_fingerprint,
        encrypted_data=cipher_text
    ))

    assert isinstance(
        server_dh_params, (_tl.ServerDHParamsOk, _tl.ServerDHParamsFail)),\
        'Step 2.1 answer was %s' % server_dh_params

    if server_dh_params.nonce != res_pq.nonce:
        raise SecurityError('Step 2 invalid nonce from server')

    if server_dh_params.server_nonce != res_pq.server_nonce:
        raise SecurityError('Step 2 invalid server nonce from server')

    if isinstance(server_dh_params, _tl.ServerDHParamsFail):
        nnh = int.from_bytes(
            sha1(new_nonce.to_bytes(32, 'little', signed=True)).digest()[4:20],
            'little', signed=True
        )
        if server_dh_params.new_nonce_hash != nnh:
            raise SecurityError('Step 2 invalid DH fail nonce from server')

    assert isinstance(server_dh_params, _tl.ServerDHParamsOk),\
        'Step 2.2 answer was %s' % server_dh_params

    # Step 3 sending: Complete DH Exchange
    key, iv = helpers.generate_key_data_from_nonce(
        res_pq.server_nonce, new_nonce
    )
    if len(server_dh_params.encrypted_answer) % 16 != 0:
        # See PR#453
        raise SecurityError('Step 3 AES block size mismatch')

    plain_text_answer = AES.decrypt_ige(
        server_dh_params.encrypted_answer, key, iv
    )

    with BinaryReader(plain_text_answer) as reader:
        reader.read(20)  # hash sum
        server_dh_inner = reader.tgread_object()
        assert isinstance(server_dh_inner, _tl.ServerDHInnerData),\
            'Step 3 answer was %s' % server_dh_inner

    if server_dh_inner.nonce != res_pq.nonce:
        raise SecurityError('Step 3 Invalid nonce in encrypted answer')

    if server_dh_inner.server_nonce != res_pq.server_nonce:
        raise SecurityError('Step 3 Invalid server nonce in encrypted answer')

    dh_prime = get_int(server_dh_inner.dh_prime, signed=False)
    g = server_dh_inner.g
    g_a = get_int(server_dh_inner.g_a, signed=False)
    time_offset = server_dh_inner.server_time - int(time.time())

    b = get_int(os.urandom(256), signed=False)
    g_b = pow(g, b, dh_prime)
    gab = pow(g_a, b, dh_prime)

    # IMPORTANT: Apart from the conditions on the Diffie-Hellman prime
    # dh_prime and generator g, both sides are to check that g, g_a and
    # g_b are greater than 1 and less than dh_prime - 1. We recommend
    # checking that g_a and g_b are between 2^{2048-64} and
    # dh_prime - 2^{2048-64} as well.
    # (https://core.telegram.org/mtproto/auth_key#dh-key-exchange-complete)
    if not (1 < g < (dh_prime - 1)):
        raise SecurityError('g is not within (1, dh_prime - 1)')

    if not (1 < g_a < (dh_prime - 1)):
        raise SecurityError('g_a is not within (1, dh_prime - 1)')

    if not (1 < g_b < (dh_prime - 1)):
        raise SecurityError('g_b is not within (1, dh_prime - 1)')

    safety_range = 2 ** (2048 - 64)
    if not (safety_range <= g_a <= (dh_prime - safety_range)):
        raise SecurityError('g_a is not within (2^{2048-64}, dh_prime - 2^{2048-64})')

    if not (safety_range <= g_b <= (dh_prime - safety_range)):
        raise SecurityError('g_b is not within (2^{2048-64}, dh_prime - 2^{2048-64})')

    # Prepare client DH Inner Data
    client_dh_inner = bytes(_tl.ClientDHInnerData(
        nonce=res_pq.nonce,
        server_nonce=res_pq.server_nonce,
        retry_id=0,  # TODO Actual retry ID
        g_b=rsa.get_byte_array(g_b)
    ))

    client_dh_inner_hashed = sha1(client_dh_inner).digest() + client_dh_inner

    # Encryption
    client_dh_encrypted = AES.encrypt_ige(client_dh_inner_hashed, key, iv)

    # Prepare Set client DH params
    dh_gen = await sender.send(_tl.fn.SetClientDHParams(
        nonce=res_pq.nonce,
        server_nonce=res_pq.server_nonce,
        encrypted_data=client_dh_encrypted,
    ))

    nonce_types = (_tl.DhGenOk, _tl.DhGenRetry, _tl.DhGenFail)
    assert isinstance(dh_gen, nonce_types), 'Step 3.1 answer was %s' % dh_gen
    name = dh_gen.__class__.__name__
    if dh_gen.nonce != res_pq.nonce:
        raise SecurityError('Step 3 invalid {} nonce from server'.format(name))

    if dh_gen.server_nonce != res_pq.server_nonce:
        raise SecurityError(
            'Step 3 invalid {} server nonce from server'.format(name))

    auth_key = AuthKey(rsa.get_byte_array(gab))
    nonce_number = 1 + nonce_types.index(type(dh_gen))
    new_nonce_hash = auth_key.calc_new_nonce_hash(new_nonce, nonce_number)

    dh_hash = getattr(dh_gen, 'new_nonce_hash{}'.format(nonce_number))
    if dh_hash != new_nonce_hash:
        raise SecurityError('Step 3 invalid new nonce hash')

    if not isinstance(dh_gen, _tl.DhGenOk):
        raise AssertionError('Step 3.2 answer was %s' % dh_gen)

    return auth_key, time_offset


def get_int(byte_array, signed=True):
    """
    Gets the specified integer from its byte array.
    This should be used by this module alone, as it works with big endian.

    :param byte_array: the byte array representing th integer.
    :param signed: whether the number is signed or not.
    :return: the integer representing the given byte array.
    """
    return int.from_bytes(byte_array, byteorder='big', signed=signed)
