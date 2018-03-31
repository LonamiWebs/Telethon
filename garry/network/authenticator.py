"""
This module contains several functions that authenticate the client machine
with Telegram's servers, effectively creating an authorization key.
"""
import os
import time
from hashlib import sha1

from ..tl.types import (
    ResPQ, PQInnerData, ServerDHParamsFail, ServerDHParamsOk,
    ServerDHInnerData, ClientDHInnerData, DhGenOk, DhGenRetry, DhGenFail
)
from .. import helpers as utils
from ..crypto import AES, AuthKey, Factorization
from ..crypto import rsa
from ..errors import SecurityError
from ..extensions import BinaryReader
from ..network import MtProtoPlainSender
from ..tl.functions import (
    ReqPqMultiRequest, ReqDHParamsRequest, SetClientDHParamsRequest
)


def do_authentication(connection, retries=5):
    """
    Performs the authentication steps on the given connection.
    Raises an error if all attempts fail.

    :param connection: the connection to be used (must be connected).
    :param retries: how many times should we retry on failure.
    :return:
    """
    if not retries or retries < 0:
        retries = 1

    last_error = None
    while retries:
        try:
            return _do_authentication(connection)
        except (SecurityError, AssertionError, NotImplementedError) as e:
            last_error = e
        retries -= 1
    raise last_error


def _do_authentication(connection):
    """
    Executes the authentication process with the Telegram servers.

    :param connection: the connection to be used (must be connected).
    :return: returns a (authorization key, time offset) tuple.
    """
    sender = MtProtoPlainSender(connection)

    # Step 1 sending: PQ Request, endianness doesn't matter since it's random
    req_pq_request = ReqPqMultiRequest(
        nonce=int.from_bytes(os.urandom(16), 'big', signed=True)
    )
    sender.send(bytes(req_pq_request))
    with BinaryReader(sender.receive()) as reader:
        req_pq_request.on_response(reader)

    res_pq = req_pq_request.result
    if not isinstance(res_pq, ResPQ):
        raise AssertionError(res_pq)

    if res_pq.nonce != req_pq_request.nonce:
        raise SecurityError('Invalid nonce from server')

    pq = get_int(res_pq.pq)

    # Step 2 sending: DH Exchange
    p, q = Factorization.factorize(pq)
    p, q = rsa.get_byte_array(min(p, q)), rsa.get_byte_array(max(p, q))
    new_nonce = int.from_bytes(os.urandom(32), 'little', signed=True)

    pq_inner_data = bytes(PQInnerData(
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
        raise SecurityError(
            'Could not find a valid key for fingerprints: {}'
            .format(', '.join(
                [str(f) for f in res_pq.server_public_key_fingerprints])
            )
        )

    req_dh_params = ReqDHParamsRequest(
        nonce=res_pq.nonce,
        server_nonce=res_pq.server_nonce,
        p=p, q=q,
        public_key_fingerprint=target_fingerprint,
        encrypted_data=cipher_text
    )
    sender.send(bytes(req_dh_params))

    # Step 2 response: DH Exchange
    with BinaryReader(sender.receive()) as reader:
        req_dh_params.on_response(reader)

    server_dh_params = req_dh_params.result
    if isinstance(server_dh_params, ServerDHParamsFail):
        raise SecurityError('Server DH params fail: TODO')

    if not isinstance(server_dh_params, ServerDHParamsOk):
        raise AssertionError(server_dh_params)

    if server_dh_params.nonce != res_pq.nonce:
        raise SecurityError('Invalid nonce from server')

    if server_dh_params.server_nonce != res_pq.server_nonce:
        raise SecurityError('Invalid server nonce from server')

    # Step 3 sending: Complete DH Exchange
    key, iv = utils.generate_key_data_from_nonce(
        res_pq.server_nonce, new_nonce
    )
    if len(server_dh_params.encrypted_answer) % 16 != 0:
        # See PR#453
        raise SecurityError('AES block size mismatch')

    plain_text_answer = AES.decrypt_ige(
        server_dh_params.encrypted_answer, key, iv
    )

    with BinaryReader(plain_text_answer) as reader:
        reader.read(20)  # hash sum
        server_dh_inner = reader.tgread_object()
        if not isinstance(server_dh_inner, ServerDHInnerData):
            raise AssertionError(server_dh_inner)

    if server_dh_inner.nonce != res_pq.nonce:
        raise SecurityError('Invalid nonce in encrypted answer')

    if server_dh_inner.server_nonce != res_pq.server_nonce:
        raise SecurityError('Invalid server nonce in encrypted answer')

    dh_prime = get_int(server_dh_inner.dh_prime, signed=False)
    g_a = get_int(server_dh_inner.g_a, signed=False)
    time_offset = server_dh_inner.server_time - int(time.time())

    b = get_int(os.urandom(256), signed=False)
    gb = pow(server_dh_inner.g, b, dh_prime)
    gab = pow(g_a, b, dh_prime)

    # Prepare client DH Inner Data
    client_dh_inner = bytes(ClientDHInnerData(
        nonce=res_pq.nonce,
        server_nonce=res_pq.server_nonce,
        retry_id=0,  # TODO Actual retry ID
        g_b=rsa.get_byte_array(gb)
    ))

    client_dh_inner_hashed = sha1(client_dh_inner).digest() + client_dh_inner

    # Encryption
    client_dh_encrypted = AES.encrypt_ige(client_dh_inner_hashed, key, iv)

    # Prepare Set client DH params
    set_client_dh = SetClientDHParamsRequest(
        nonce=res_pq.nonce,
        server_nonce=res_pq.server_nonce,
        encrypted_data=client_dh_encrypted,
    )
    sender.send(bytes(set_client_dh))

    # Step 3 response: Complete DH Exchange
    with BinaryReader(sender.receive()) as reader:
        set_client_dh.on_response(reader)

    dh_gen = set_client_dh.result
    if isinstance(dh_gen, DhGenOk):
        if dh_gen.nonce != res_pq.nonce:
            raise SecurityError('Invalid nonce from server')

        if dh_gen.server_nonce != res_pq.server_nonce:
            raise SecurityError('Invalid server nonce from server')

        auth_key = AuthKey(rsa.get_byte_array(gab))
        new_nonce_hash = int.from_bytes(
            auth_key.calc_new_nonce_hash(new_nonce, 1), 'little', signed=True
        )

        if dh_gen.new_nonce_hash1 != new_nonce_hash:
            raise SecurityError('Invalid new nonce hash')

        return auth_key, time_offset

    elif isinstance(dh_gen, DhGenRetry):
        raise NotImplementedError('DhGenRetry')

    elif isinstance(dh_gen, DhGenFail):
        raise NotImplementedError('DhGenFail')

    else:
        raise NotImplementedError('DH Gen unknown: {}'.format(dh_gen))


def get_int(byte_array, signed=True):
    """
    Gets the specified integer from its byte array.
    This should be used by this module alone, as it works with big endian.

    :param byte_array: the byte array representing th integer.
    :param signed: whether the number is signed or not.
    :return: the integer representing the given byte array.
    """
    return int.from_bytes(byte_array, byteorder='big', signed=signed)
