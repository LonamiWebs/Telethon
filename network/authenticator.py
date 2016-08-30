# This file is based on TLSharp
# https://github.com/sochix/TLSharp/blob/master/TLSharp.Core/Auth/Authenticator.cs
# https://github.com/sochix/TLSharp/blob/master/TLSharp.Core/Auth/Step1_PQRequest.cs
# https://github.com/sochix/TLSharp/blob/master/TLSharp.Core/Auth/Step2_DHExchange.cs
# https://github.com/sochix/TLSharp/blob/master/TLSharp.Core/Auth/Step3_CompleteDHExchange.cs

from network.mtproto_plain_sender import MtProtoPlainSender
from utils.binary_writer import BinaryWriter
from utils.binary_reader import BinaryReader
from utils.factorizator import Factorizator
from utils.auth_key import AuthKey
import utils.helpers as utils
import time
import pyaes
import rsa


def do_authentication(transport):
    sender = MtProtoPlainSender(transport)

    # Step 1 sending: PQ Request
    nonce = utils.generate_random_bytes(16)
    with BinaryWriter() as writer:
        writer.write_int(0x60469778)  # Constructor number
        writer.write(nonce)
        sender.send(writer.get_bytes())

    # Step 1 response: PQ Request
    pq, pq_bytes, server_nonce, fingerprints = None, None, None, []
    with BinaryReader(sender.receive()) as reader:
        response_code = reader.read_int(signed=False)
        if response_code != 0x05162463:
            raise AssertionError('Invalid response code: {}'.format(hex(response_code)))

        nonce_from_server = reader.read(16)
        if nonce_from_server != nonce:
            raise AssertionError('Invalid nonce from server')

        server_nonce = reader.read(16)

        pq_bytes = reader.tgread_bytes()
        pq = int.from_bytes(pq_bytes, byteorder='big')

        vector_id = reader.read_int()
        if vector_id != 0x1cb5c415:
            raise AssertionError('Invalid vector constructor ID: {}'.format(hex(response_code)))

        fingerprints = []
        fingerprint_count = reader.read_int()
        for _ in range(fingerprint_count):
            fingerprints.append(reader.read(8))

    # Step 2 sending: DH Exchange
    new_nonce = utils.generate_random_bytes(32)
    p, q = Factorizator.factorize(pq)
    with BinaryWriter() as pq_inner_data_writer:
        pq_inner_data_writer.write_int(0x83c95aec)  # PQ Inner Data
        pq_inner_data_writer.tgwrite_bytes(utils.get_byte_array(pq, signed=False))
        pq_inner_data_writer.tgwrite_bytes(utils.get_byte_array(min(p, q), signed=False))
        pq_inner_data_writer.tgwrite_bytes(utils.get_byte_array(max(p, q), signed=False))
        pq_inner_data_writer.write(nonce)
        pq_inner_data_writer.write(server_nonce)
        pq_inner_data_writer.write(new_nonce)

        cipher_text, target_fingerprint = None, None
        for fingerprint in fingerprints:
            cipher_text = rsa.encrypt(str(fingerprint, encoding='utf-8').replace('-', ''),
                                      pq_inner_data_writer.get_bytes())

            if cipher_text is not None:
                target_fingerprint = fingerprint
                break

        if cipher_text is None:
            raise AssertionError('Could not find a valid key for fingerprints: {}'
                                 .format(', '.join([str(f, encoding='utf-8') for f in fingerprints])))

        with BinaryWriter() as req_dh_params_writer:
            req_dh_params_writer.write_int(0xd712e4be)  # Req DH Params
            req_dh_params_writer.write(nonce)
            req_dh_params_writer.write(server_nonce)
            req_dh_params_writer.tgwrite_bytes(utils.get_byte_array(min(p, q), signed=False))
            req_dh_params_writer.tgwrite_bytes(utils.get_byte_array(max(p, q), signed=False))
            req_dh_params_writer.Write(target_fingerprint)
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
            raise AssertionError('Invalid response code: {}'.format(hex(response_code)))

        nonce_from_server = reader.read(16)
        if nonce_from_server != nonce:
            raise NotImplementedError('Invalid nonce from server')

        server_nonce_from_server = reader.read(16)
        if server_nonce_from_server != server_nonce:
            raise NotImplementedError('Invalid server nonce from server')

        encrypted_answer = reader.tgread_bytes()

    # Step 3 sending: Complete DH Exchange
    key, iv = utils.generate_key_data_from_nonces(server_nonce, new_nonce)
    aes = pyaes.AESModeOfOperationCFB(key, iv, 16)
    plain_text_answer = aes.decrypt(encrypted_answer)

    g, dh_prime, ga, time_offset = None, None, None, None
    with BinaryReader(plain_text_answer.encode('ascii')) as dh_inner_data_reader:
        hashsum = dh_inner_data_reader.read(20)
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
        dh_prime = int.from_bytes(dh_inner_data_reader.tgread_bytes(), byteorder='big', signed=True)
        ga = int.from_bytes(dh_inner_data_reader.tgread_bytes(), byteorder='big', signed=True)

        server_time = dh_inner_data_reader.read_int()
        time_offset = server_time - int(time.time() * 1000)  # Multiply by 1000 to get milliseconds

    b = int.from_bytes(utils.generate_random_bytes(2048), byteorder='big')
    gb = pow(g, b, dh_prime)
    gab = pow(ga, b, dh_prime)

    # Prepare client DH Inner Data
    with BinaryWriter() as client_dh_inner_data_writer:
        client_dh_inner_data_writer.write_int(0x6643b654)  # Client DH Inner Data
        client_dh_inner_data_writer.write(nonce)
        client_dh_inner_data_writer.write(server_nonce)
        client_dh_inner_data_writer.write_long(0)  # TODO retry_id
        client_dh_inner_data_writer.tgwrite_bytes(utils.get_byte_array(gb, signed=False))

        with BinaryWriter() as client_dh_inner_data_with_hash_writer:
            client_dh_inner_data_with_hash_writer.write(utils.sha1(client_dh_inner_data_writer.get_bytes()))
            client_dh_inner_data_with_hash_writer.write(client_dh_inner_data_writer.get_bytes())
            client_dh_inner_data_bytes = client_dh_inner_data_with_hash_writer.get_bytes()

    # Encryption
    client_dh_inner_data_encrypted_bytes = aes.encrypt(client_dh_inner_data_bytes)

    # Prepare Set client DH params
    with BinaryWriter() as set_client_dh_params_writer:
        set_client_dh_params_writer.write_int(0xf5045f1f)
        set_client_dh_params_writer.write(nonce)
        set_client_dh_params_writer.write(server_nonce)
        set_client_dh_params_writer.tgwrite_bytes(client_dh_inner_data_encrypted_bytes)

        set_client_dh_params_bytes = set_client_dh_params_writer.get_bytes()
        sender.send(set_client_dh_params_bytes)

    # Step 3 response: Complete DH Exchange
    with BinaryReader(sender.receive()) as reader:
        code = reader.read_int(signed=False)
        if code == 0x3bcbf734:  # DH Gen OK
            nonce_from_server = reader.read(16)
            if nonce_from_server != nonce:
                raise NotImplementedError('Invalid nonce from server')

            server_nonce_from_server = reader.read(16)
            if server_nonce_from_server != server_nonce:
                raise NotImplementedError('Invalid server nonce from server')

            new_nonce_hash1 = reader.read(16)
            auth_key = AuthKey(gab)

            new_nonce_hash_calculated = auth_key.calc_new_nonce_hash(new_nonce, 1)
            if new_nonce_hash1 != new_nonce_hash_calculated:
                raise AssertionError('Invalid new nonce hash')

            return auth_key, time_offset

        elif code == 0x46dc1fb9:  # DH Gen Retry
            raise NotImplementedError('dh_gen_retry')

        elif code == 0xa69dae02:  # DH Gen Fail
            raise NotImplementedError('dh_gen_fail')

        else:
            raise AssertionError('DH Gen unknown: {}'.format(hex(code)))
