import os
import time
from hashlib import sha1

from .. import helpers as utils
from ..crypto import AES, RSA, AuthKey, Factorization
from ..network import MtProtoPlainSender
from ..extensions import BinaryReader, BinaryWriter


def do_authentication(transport):
    """Executes the authentication process with the Telegram servers.
       If no error is raised, returns both the authorization key and the
       time offset.
    """
    sender = MtProtoPlainSender(transport)
    sender.connect()

    # Step 1 sending: PQ Request
    nonce = os.urandom(16)
    with BinaryWriter() as writer:
        writer.write_int(0x60469778, signed=False)  # Constructor number
        writer.write(nonce)
        sender.send(writer.get_bytes())

    # Step 1 response: PQ Request
    pq, pq_bytes, server_nonce, fingerprints = None, None, None, []
    with BinaryReader(sender.receive()) as reader:
        response_code = reader.read_int(signed=False)
        if response_code != 0x05162463:
            raise AssertionError('Invalid response code: {}'.format(
                hex(response_code)))

        nonce_from_server = reader.read(16)
        if nonce_from_server != nonce:
            raise AssertionError('Invalid nonce from server')

        server_nonce = reader.read(16)

        pq_bytes = reader.tgread_bytes()
        pq = get_int(pq_bytes)

        vector_id = reader.read_int()
        if vector_id != 0x1cb5c415:
            raise AssertionError('Invalid vector constructor ID: {}'.format(
                hex(response_code)))

        fingerprints = []
        fingerprint_count = reader.read_int()
        for _ in range(fingerprint_count):
            fingerprints.append(reader.read(8))

    # Step 2 sending: DH Exchange
    new_nonce = os.urandom(32)
    p, q = Factorization.factorize(pq)
    with BinaryWriter() as pq_inner_data_writer:
        pq_inner_data_writer.write_int(
            0x83c95aec, signed=False)  # PQ Inner Data
        pq_inner_data_writer.tgwrite_bytes(get_byte_array(pq, signed=False))
        pq_inner_data_writer.tgwrite_bytes(
            get_byte_array(
                min(p, q), signed=False))
        pq_inner_data_writer.tgwrite_bytes(
            get_byte_array(
                max(p, q), signed=False))
        pq_inner_data_writer.write(nonce)
        pq_inner_data_writer.write(server_nonce)
        pq_inner_data_writer.write(new_nonce)

        cipher_text, target_fingerprint = None, None
        for fingerprint in fingerprints:
            cipher_text = RSA.encrypt(
                get_fingerprint_text(fingerprint),
                pq_inner_data_writer.get_bytes())

            if cipher_text is not None:
                target_fingerprint = fingerprint
                break

        if cipher_text is None:
            raise AssertionError(
                'Could not find a valid key for fingerprints: {}'
                .format(', '.join([get_fingerprint_text(f)
                                   for f in fingerprints])))

        with BinaryWriter() as req_dh_params_writer:
            req_dh_params_writer.write_int(
                0xd712e4be, signed=False)  # Req DH Params
            req_dh_params_writer.write(nonce)
            req_dh_params_writer.write(server_nonce)
            req_dh_params_writer.tgwrite_bytes(
                get_byte_array(
                    min(p, q), signed=False))
            req_dh_params_writer.tgwrite_bytes(
                get_byte_array(
                    max(p, q), signed=False))
            req_dh_params_writer.write(target_fingerprint)
            req_dh_params_writer.tgwrite_bytes(cipher_text)

            req_dh_params_bytes = req_dh_params_writer.get_bytes()
            sender.send(req_dh_params_bytes)

    # Step 2 response: DH Exchange
    encrypted_answer = None
    with BinaryReader(sender.receive()) as reader:
        response_code = reader.read_int(signed=False)

        if response_code == 0x79cb045d:
            raise AssertionError('Server DH params fail: TODO')

        if response_code != 0xd0e8075c:
            raise AssertionError('Invalid response code: {}'.format(
                hex(response_code)))

        nonce_from_server = reader.read(16)
        if nonce_from_server != nonce:
            raise NotImplementedError('Invalid nonce from server')

        server_nonce_from_server = reader.read(16)
        if server_nonce_from_server != server_nonce:
            raise NotImplementedError('Invalid server nonce from server')

        encrypted_answer = reader.tgread_bytes()

    # Step 3 sending: Complete DH Exchange
    key, iv = utils.generate_key_data_from_nonce(server_nonce, new_nonce)
    plain_text_answer = AES.decrypt_ige(encrypted_answer, key, iv)

    g, dh_prime, ga, time_offset = None, None, None, None
    with BinaryReader(plain_text_answer) as dh_inner_data_reader:
        dh_inner_data_reader.read(20)  # hash sum
        code = dh_inner_data_reader.read_int(signed=False)
        if code != 0xb5890dba:
            raise AssertionError('Invalid DH Inner Data code: {}'.format(code))

        nonce_from_server1 = dh_inner_data_reader.read(16)
        if nonce_from_server1 != nonce:
            raise AssertionError('Invalid nonce in encrypted answer')

        server_nonce_from_server1 = dh_inner_data_reader.read(16)
        if server_nonce_from_server1 != server_nonce:
            raise AssertionError('Invalid server nonce in encrypted answer')

        g = dh_inner_data_reader.read_int()
        dh_prime = get_int(dh_inner_data_reader.tgread_bytes(), signed=False)
        ga = get_int(dh_inner_data_reader.tgread_bytes(), signed=False)

        server_time = dh_inner_data_reader.read_int()
        time_offset = server_time - int(time.time())

    b = get_int(os.urandom(2048), signed=False)
    gb = pow(g, b, dh_prime)
    gab = pow(ga, b, dh_prime)

    # Prepare client DH Inner Data
    with BinaryWriter() as client_dh_inner_data_writer:
        client_dh_inner_data_writer.write_int(
            0x6643b654, signed=False)  # Client DH Inner Data
        client_dh_inner_data_writer.write(nonce)
        client_dh_inner_data_writer.write(server_nonce)
        client_dh_inner_data_writer.write_long(0)  # TODO retry_id
        client_dh_inner_data_writer.tgwrite_bytes(
            get_byte_array(
                gb, signed=False))

        with BinaryWriter() as client_dh_inner_data_with_hash_writer:
            client_dh_inner_data_with_hash_writer.write(
                sha1(client_dh_inner_data_writer.get_bytes()).digest())

            client_dh_inner_data_with_hash_writer.write(
                client_dh_inner_data_writer.get_bytes())

            client_dh_inner_data_bytes = \
                client_dh_inner_data_with_hash_writer.get_bytes()

    # Encryption
    client_dh_inner_data_encrypted_bytes = AES.encrypt_ige(
        client_dh_inner_data_bytes, key, iv)

    # Prepare Set client DH params
    with BinaryWriter() as set_client_dh_params_writer:
        set_client_dh_params_writer.write_int(0xf5045f1f, signed=False)
        set_client_dh_params_writer.write(nonce)
        set_client_dh_params_writer.write(server_nonce)
        set_client_dh_params_writer.tgwrite_bytes(
            client_dh_inner_data_encrypted_bytes)

        set_client_dh_params_bytes = set_client_dh_params_writer.get_bytes()
        sender.send(set_client_dh_params_bytes)

    # Step 3 response: Complete DH Exchange
    with BinaryReader(sender.receive()) as reader:
        # Everything read from the server, disconnect now
        sender.disconnect()

        code = reader.read_int(signed=False)
        if code == 0x3bcbf734:  # DH Gen OK
            nonce_from_server = reader.read(16)
            if nonce_from_server != nonce:
                raise NotImplementedError('Invalid nonce from server')

            server_nonce_from_server = reader.read(16)
            if server_nonce_from_server != server_nonce:
                raise NotImplementedError('Invalid server nonce from server')

            new_nonce_hash1 = reader.read(16)
            auth_key = AuthKey(get_byte_array(gab, signed=False))

            new_nonce_hash_calculated = auth_key.calc_new_nonce_hash(new_nonce,
                                                                     1)
            if new_nonce_hash1 != new_nonce_hash_calculated:
                raise AssertionError('Invalid new nonce hash')

            return auth_key, time_offset

        elif code == 0x46dc1fb9:  # DH Gen Retry
            raise NotImplementedError('dh_gen_retry')

        elif code == 0xa69dae02:  # DH Gen Fail
            raise NotImplementedError('dh_gen_fail')

        else:
            raise AssertionError('DH Gen unknown: {}'.format(hex(code)))


def get_fingerprint_text(fingerprint):
    """Gets a fingerprint text in 01-23-45-67-89-AB-CD-EF format (no hyphens)"""
    return ''.join(hex(b)[2:].rjust(2, '0').upper() for b in fingerprint)


# The following methods operate in big endian (unlike most of Telegram API) because:
# > "...pq is a representation of a natural number (in binary *big endian* format)..."
# > "...current value of dh_prime equals (in *big-endian* byte order)..."
# Reference: https://core.telegram.org/mtproto/auth_key
def get_byte_array(integer, signed):
    """Gets the arbitrary-length byte array corresponding to the given integer"""
    bits = integer.bit_length()
    byte_length = (bits + 8 - 1) // 8  # 8 bits per byte
    return int.to_bytes(
        integer, length=byte_length, byteorder='big', signed=signed)


def get_int(byte_array, signed=True):
    """Gets the specified integer from its byte array. This should be used by the authenticator,
       who requires the data to be in big endian"""
    return int.from_bytes(byte_array, byteorder='big', signed=signed)
