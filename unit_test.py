import unittest
import socket
import threading
import random
import utils.helpers as utils

from network.tcp_client import TcpClient
from utils.binary_reader import BinaryReader
from utils.binary_writer import BinaryWriter
from utils.factorizator import Factorizator
from utils.aes import AES


host = 'localhost'
port = random.randint(50000, 60000)  # Arbitrary non-privileged port


def run_server_echo_thread():
    def server_thread():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', port))
            s.listen(1)
            conn, addr = s.accept()
            with conn:
                data = conn.recv(16)
                conn.send(data)

    server = threading.Thread(target=server_thread)
    server.start()


def get_representation(bytez):
    return '-'.join(hex(b)[2:].rjust(2, '0').upper() for b in bytez)


def get_bytes(representation):
    return bytes([int(b, 16) for b in representation.split('-')])


class UnitTest(unittest.TestCase):
    @staticmethod
    def test_tcp_client():
        client = TcpClient()
        run_server_echo_thread()
        
        try:
            client.connect(host, port)
        except:
            raise AssertionError('Could connect to the server')

        try:
            client.write('Unit testing...'.encode('ascii'))
        except:
            raise AssertionError('Could not send a message to the server')

        try:
            client.read(16)
        except:
            raise AssertionError('Could not read a message to the server')

        try:
            client.close()
        except:
            raise AssertionError('Could not close the client')

    @staticmethod
    def test_binary_writer_reader():
        # Test that we can write and read properly
        with BinaryWriter() as writer:
            writer.write_byte(1)
            writer.write_int(5)
            writer.write_long(13)
            writer.write_float(17.0)
            writer.write_double(25.0)
            writer.write(bytes([26, 27, 28, 29, 30, 31, 32]))
            writer.write_large_int(2**127, 128, signed=False)

            data = writer.get_bytes()
            assert data is not None, 'Example Data should not be None'
            assert len(data) == 48, 'Example data length should be 48, but is {}'.format(len(data))

        with BinaryReader(data) as reader:
            value = reader.read_byte()
            assert value == 1, 'Example byte should be 1 but is {}'.format(value)

            value = reader.read_int()
            assert value == 5, 'Example integer should be 5 but is {}'.format(value)

            value = reader.read_long()
            assert value == 13, 'Example long integer should be 13 but is {}'.format(value)

            value = reader.read_float()
            assert value == 17.0, 'Example float should be 17.0 but is {}'.format(value)

            value = reader.read_double()
            assert value == 25.0, 'Example double should be 25.0 but is {}'.format(value)

            value = reader.read(7)
            assert value == bytes([26, 27, 28, 29, 30, 31, 32]), 'Example bytes should be {} but is {}'\
                .format(bytes([26, 27, 28, 29, 30, 31, 32]), value)

            value = reader.read_large_int(128, signed=False)
            assert value == 2**127, 'Example large integer should be {} but is {}'.format(2**127, value)

        # Test Telegram that types are written right
        with BinaryWriter() as writer:
            writer.write_int(0x60469778)
            buffer = writer.get_bytes()
            valid = b'\x78\x97\x46\x60'  # Tested written bytes using TLSharp and C#'s MemoryStream

            assert buffer == valid, "Written type should be {} but is {}".format(list(valid), list(buffer))

    @staticmethod
    def test_binary_tgwriter_tgreader():
        string = 'Testing Telegram strings, this should work properly!'
        small_data = utils.generate_random_bytes(20)
        large_data = utils.generate_random_bytes(1024)

        with BinaryWriter() as writer:
            writer.tgwrite_string(string)
            writer.tgwrite_bytes(small_data)
            writer.tgwrite_bytes(large_data)

            data = writer.get_bytes()
            assert data is not None, 'Example Data should not be None'

        with BinaryReader(data) as reader:
            value = reader.tgread_string()
            assert value == string, 'Example string should be {} but is {}'.format(string, value)

            value = reader.tgread_bytes()
            assert value == small_data, 'Example bytes should be {} but is {}'.format(small_data, value)

            value = reader.tgread_bytes()
            assert value == large_data, 'Example bytes should be {} but is {}'.format(large_data, value)

    @staticmethod
    def test_factorizator():
        pq = 3118979781119966969
        p, q = Factorizator.factorize(pq)

        assert p == 1719614201, 'Factorized pair did not yield the correct result'
        assert q == 1813767169, 'Factorized pair did not yield the correct result'

    @staticmethod
    def test_to_byte_array():
        for value, real in zip(
                [3118979781119966969,  # PQ
                 1667024975687354561,  # PQ
                 1148985737, 1450866553],  # Min, Max

                ['2B-48-D7-95-FB-47-FE-F9',  # PQ
                 '17-22-76-62-13-8C-88-C1',  # PQ
                 '44-7C-21-89', '56-7A-77-79']  # Min, Max
        ):
            current = get_representation(utils.get_byte_array(value, signed=True))
            assert real == current, 'Invalid byte array representation (expected {}, got {})'.format(current, real)

    @staticmethod
    def test_sha1():
        string = 'Example string'
        data = get_representation(string.encode('utf-8'))
        real = '45-78-61-6D-70-6C-65-20-73-74-72-69-6E-67'
        assert data == real, 'Invalid string representation (should be {}, but is {})'.format(real, data)

        hashsum = get_representation(utils.sha1(get_bytes(data)))
        real = '0A-54-92-7C-8D-06-3A-29-99-04-8E-F8-6A-3F-C4-8E-D3-7D-6D-39'
        assert hashsum == real, 'Invalid sha1 hashsum representation (should be {}, but is {})'.format(real, data)

    @staticmethod
    def test_bytes_to_int():
        bytez = b'\x01\x23\x45\x67\x89\xab\xcd\xef'

        reprs = get_representation(bytez)
        real = '01-23-45-67-89-AB-CD-EF'
        assert reprs == real, 'Invalid bytes representation (should be {} but is {})'.format(real, reprs)
        assert bytez == get_bytes(reprs), 'Invalid representation to bytes conversion'

        value = int.from_bytes(bytez, byteorder='big', signed=True)
        real = 81985529216486895
        assert value == real, 'Invalid bytes to int conversion (should be {} but is {})'.format(real, value)

        # Now test more cases
        for repr, real in zip(
            ['24-9D-FE-49-20-45-DF-C3', '60-44-F3-33', '61-5F-61-31'],
            [2638544546736496579, 1615131443, 1633640753]
        ):
            bytez = get_bytes(repr)
            if len(bytez) > 8:
                value = int.from_bytes(bytez, byteorder='little', signed=True)
            else:
                value = int.from_bytes(bytez, byteorder='big', signed=True)
            assert value == real, 'Invalid bytes to int conversion (should be {} but is {})'.format(real, value)

    @staticmethod
    def test_aes_decrypt():
        cipher_text = get_bytes('EF-5F-5D-57-7B-A5-95-B0-1D-B7-BF-E5-09-AC-64-5E-F9-ED-E3-28-FB-D7-59-78-16-F8-74-4A-51-A6-10-16-F5-EF-99-0B-E6-CA-A7-9D-FA-DD-7B-CD-39-BF-FB-F0-D4-B6-09-50-76-78-9D-6F-87-DD-57-33-B7-F4-48-4F-C1-78-73-66-22-E1-65-74-E6-7B-4F-EB-99-7B-2D-58-94-62-10-2A-A2-C8-95-B4-D4-EE-2E-C9-44-DA-54-EE-7A-86-72-34-14-54-4F-E3-F9-C5-3A-3F-7E-C3-28-29-2F-19-D4-40-DA-D4-E6-11-A4-6D-A7-8A-20-0A-C4-2A-55-DD-4A-1A-D1-57-18-86-4C-0F-BC-9C-F6-2C-D5-E1-FA-D4-08-48-F9-B2-49-61-BA-30-6A-9F-E0-3E-55-66-E0-57-55-8A-02-57-28-E1-C8-BD-4A-F7-26-6A-6E-2F-93-76-57-C4-E5-F3-96-F3-79-17-B8-16-15-C1-A4-21-11-0F-9A-4D-92-BB-DF-2F-8E-4C-3E-88-D6-41-CC-91-D4-BA-FF-5A-F1-D9-2C-9C-FA-F3-DD-DB-03-B0-1B-1C-32-8C-9C-DE-96-FA-AE-40-9C-F5-AC-15-BF-11-17-D3-0F-E4-F4-C5-46-E7-27-3C-47-91-FD-02-AC-FC-7F-84-0D-4A-BC-43-2A-7E-0E-B9-BD-93-8E-0F-C9-1B-CF-C3-61-EA-2A-73-D8-00-3C-6E-BA-33-63-A6-24-16-AB-AB-11-93-3D-7B-20-29-C6-37-43-CF-78-C7-25-CE-03-02-0C-58-B3-34-24-61-06-FE-DD-00-65-BC-51-99-6E-08-51-8B-8D-83-CA-F1-36-ED-94-F6-FF-19-30-1C-6D-4E-6F-8C-59-08-2D-60-E6-3D-A8-39-C2-FE-96-2D-CF-AD-15-F5-68-B1-5B-2A-2F-6D-86-92-D9-F8-45-4F-09-80-01-3C-D1-8B-37-88-AA-52-02-58-18-7B-B5-86-60-BE-2C-E6-EE-3D-85-02-F9-CC-09-4A-44-55-73-24-A1-9B-01-ED-B1-FD-FF-C8-E1-F4-78-A9-DB-DD-F0-50-2F-A7-AB-EF-3C-0F-FC-82-5B-D5-35-E0-32-60-2F-F1-A3-DF-BE-70-68-F5-1A-AB-21-55-34-A4-45-86-B2-75-36-D1-50-36-DC-4B-78-5F-7D-44-F9-83-A4-A3-68-E9-4B-08-FA-7F-55-85-55-31-35-E5-C1-14-A4-E3-E2-AC-8A-2D-64-36-6F-46-4E-B1-AF-FE-66-BF-38-DD-1D-40-BC-DA-3F-0A-48-91-BD-09-84-B6-42-35-2A-E9-3A-57-63-92-BB-94-44-91-C7-C4-46-79-C4-60-7F-95-88-53-24-CF-CE-0A-4C-28-9B-B9-4F-10-68-CC-E3-A5-3F-F1-A1-43-4A-C8-FF-98-AC-F5-BF-36-7F-08-01-05-02-2F-C4-3D-EA-F9-0B-3E-99-FD-3A-C2-03-E7-D3-CE-79-2D-EE-F4-01-C8-6B-4B-AA-81-BA-49-D1-87-84-72-32-7F-6B-7F')
        key = get_bytes('23-D7-11-75-77-78-5D-74-6F-74-C4-23-D3-99-66-E7-77-8B-5A-92-94-A5-88-C2-C3-D4-46-B7-F1-0C-D7-FA')
        iv = get_bytes('F8-DC-50-26-71-C3-56-72-D7-07-78-17-57-D3-B6-5D-A6-EB-02-DB-7D-73-0A-0B-1C-29-15-40-CC-6C-03-7E')

        plain_text = AES.decrypt_ige(cipher_text, key, iv)
        real = get_bytes('FB-17-EB-54-86-B6-49-1C-DF-D8-24-E6-D9-82-37-44-66-18-84-9F-BA-0D-89-B5-81-0D-47-B2-1B-CB-56-3F-7F-69-3A-22-0A-30-39-71-EE-1F-40-B2-A7-1A-4B-BD-76-7E-7A-FD-20-68-58-5F-03-00-00-00-FE-00-01-00-C7-1C-AE-B9-C6-B1-C9-04-8E-6C-52-2F-70-F1-3F-73-98-0D-40-23-8E-3E-21-C1-49-34-D0-37-56-3D-93-0F-48-19-8A-0A-A7-C1-40-58-22-94-93-D2-25-30-F4-DB-FA-33-6F-6E-0A-C9-25-13-95-43-AE-D4-4C-CE-7C-37-20-FD-51-F6-94-58-70-5A-C6-8C-D4-FE-6B-6B-13-AB-DC-97-46-51-29-69-32-84-54-F1-8F-AF-8C-59-5F-64-24-77-FE-96-BB-2A-94-1D-5B-CD-1D-4A-C8-CC-49-88-07-08-FA-9B-37-8E-3C-4F-3A-90-60-BE-E6-7C-F9-A4-A4-A6-95-81-10-51-90-7E-16-27-53-B5-6B-0F-6B-41-0D-BA-74-D8-A8-4B-2A-14-B3-14-4E-0E-F1-28-47-54-FD-17-ED-95-0D-59-65-B4-B9-DD-46-58-2D-B1-17-8D-16-9C-6B-C4-65-B0-D6-FF-9C-A3-92-8F-EF-5B-9A-E4-E4-18-FC-15-E8-3E-BE-A0-F8-7F-A9-FF-5E-ED-70-05-0D-ED-28-49-F4-7B-F9-59-D9-56-85-0C-E9-29-85-1F-0D-81-15-F6-35-B1-05-EE-2E-4E-15-D0-4B-24-54-BF-6F-4F-AD-F0-34-B1-04-03-11-9C-D8-E3-B9-2F-CC-5B-FE-00-01-00-22-8A-8F-62-58-9E-D1-9F-4B-53-EC-FB-22-E0-52-6B-8E-09-2E-B6-4B-90-53-30-A7-1F-52-1F-5B-3C-8F-AC-12-5B-D3-35-22-2A-1E-3E-9F-BD-33-73-B3-5C-1A-A6-8E-01-35-B4-8C-92-AE-D9-A0-86-6C-EF-CA-C9-09-4E-3B-B8-E5-F6-76-EE-F9-E7-CE-F1-DF-9E-F1-2E-92-55-DF-CF-80-68-70-AD-D1-AB-B2-34-54-E0-BF-38-A6-F4-C4-5B-64-96-8F-C7-14-18-84-7A-0A-44-38-56-1A-E4-9E-16-81-9D-AF-CC-A5-0E-17-D1-9E-DB-DE-DD-14-7D-04-71-99-06-32-3E-92-CE-D4-6E-76-10-DF-17-D9-2E-97-6A-F0-81-CC-ED-D5-20-10-60-AD-D8-7B-C2-FB-7D-87-CD-1E-B7-0E-28-1A-78-61-9C-8A-CA-81-A0-03-B2-40-7F-AE-BB-E3-21-96-74-01-A6-E2-C0-D8-17-C9-19-78-AD-1C-51-12-DC-29-8F-50-CA-8A-2F-56-89-A4-AC-E0-0F-C1-71-E4-C7-33-71-AE-83-30-59-D1-33-C2-D6-A6-F1-E8-FC-1F-77-3D-ED-E9-BF-B5-1C-6F-C0-9E-81-4B-B2-5A-51-C3-94-6B-BD-AD-5C-FF-DD-4B-0C-DB-E8-DA-0D-CB-57-B5-AC-D0-95-9E-FC-8F-F8')
        assert  plain_text == real, 'Decrypted text does not equal the real value (expected "{}", got "{}")'\
            .format(get_representation(real), get_representation(plain_text))

    @staticmethod
    def test_aes_encrypt():
        original_text = get_bytes('CD-B7-90-A9-61-41-F7-AD-A2-F9-FA-68-A4-D9-F2-5D-D6-6A-2E-40-54-B6-43-66-81-0D-47-B2-1B-CB-56-3F-7F-69-3A-22-0A-30-39-71-EE-1F-40-B2-A7-1A-4B-BD-76-7E-7A-FD-20-68-58-5F-00-00-00-00-00-00-00-00-FE-00-01-00-53-5B-3B-61-71-BC-C5-2D-2C-E3-D3-DB-4E-BF-BC-C0-3A-D0-90-89-C5-2E-EB-86-10-B9-B4-4B-D9-CF-00-DD-DA-D9-12-5E-27-DD-00-D2-61-E2-8A-93-97-30-38-0E-AC-49-C5-A2-7A-C8-67-6B-2C-B0-3C-95-BA-E2-C3-AC-6D-F7-87-7E-0F-9F-F1-A1-FD-87-81-04-C5-F0-14-35-E6-67-5A-E4-4E-57-A8-8D-C2-66-AF-F9-0B-82-13-CD-BC-FF-26-68-90-81-FA-26-34-80-B5-A7-C3-69-15-B1-31-BE-46-C2-B7-14-6B-75-B8-F2-71-6A-27-5B-3B-30-CF-A9-97-65-C6-E5-7D-46-EC-12-D3-6D-8F-64-58-03-1E-66-24-D5-87-9A-8B-CE-E3-D1-71-9B-F2-A9-49-19-69-B4-0A-D0-97-0E-91-5E-B0-F3-C2-FB-FF-AC-1F-CD-30-7E-C0-79-9F-DE-E0-85-17-16-13-10-FF-E8-24-B3-71-B5-C2-BC-72-B3-39-DB-53-D3-52-CB-6C-48-19-6D-CA-98-FB-C2-D4-24-6F-FD-8C-68-31-2F-C9-F4-6F-9B-55-9B-A5-6D-B9-54-D0-53-BC-8B-EC-4B-3F-D2-3C-E9-5E-34-79-80-9A-D2-8C-B9-5F-95-7A-46-72-11-4E-E6')
        key = get_bytes('23-D7-11-75-77-78-5D-74-6F-74-C4-23-D3-99-66-E7-77-8B-5A-92-94-A5-88-C2-C3-D4-46-B7-F1-0C-D7-FA')
        iv = get_bytes('F8-DC-50-26-71-C3-56-72-D7-07-78-17-57-D3-B6-5D-A6-EB-02-DB-7D-73-0A-0B-1C-29-15-40-CC-6C-03-7E')

        cipher_text = AES.encrypt_ige(original_text, key, iv)
        real = get_bytes('57-A9-1C-BB-4A-B5-C7-B1-51-9E-A9-24-15-94-4B-63-CB-2F-50-93-B7-54-11-D8-F1-77-13-AE-DE-58-12-AF-C2-E1-10-1D-2C-38-7D-DD-A2-BD-6B-43-84-7E-B1-E5-51-69-62-36-A1-86-8D-02-25-B9-AA-0B-E2-32-13-2A-0F-D1-58-67-47-07-C9-FE-E0-0F-EE-EC-92-B8-65-BD-C4-69-31-B6-10-4E-8F-20-B6-8F-72-79-A0-A3-8F-63-37-4B-95-5F-A4-B0-E6-EE-49-BE-76-47-3E-F9-FF-AA-F6-B7-16-CD-24-09-B1-63-26-02-13-B8-99-BD-19-7F-E2-A5-91-BE-52-86-FF-EA-C9-05-3C-D6-19-AE-E6-D1-25-7F-38-AF-66-CF-F8-B7-E6-53-E3-F6-98-0D-EF-A8-BA-97-6F-20-09-69-29-73-12-5E-0F-77-10-DC-22-BB-23-25-1D-53-A6-10-26-EB-EB-5E-C4-86-04-F5-30-5B-BA-53-AE-EA-84-28-34-91-75-B8-F2-0B-74-D1-00-3A-7E-FE-F0-B5-BE-0E-86-21-61-5F-81-75-23-49-45-CB-07-57-78-AB-9B-80-A2-0A-46-DB-35-49-6A-08-5B-8B-55-4E-6E-1B-E0-E0-3E-E7-2A-06-A0-5D-4F-EA-71-1A-24-F4-F4-AF-95-4B-F2-9A-C5-FD-7F-6A-DD-61-2D-B3-29-DB-5B-D9-A8-CF-60-8F-36-85-04-B5-85-3F-78-EB-09-0C-B4-F4-2D-B8-67-71-2A-4B-1B-08-0C-18-A2-9E-30-13-0C-23-18-7A-43-73-D3-DC-38-F5-9A-4A-08-28-BD-A2-DC-A8-70-33-63-9E-A9-72-DF-72-A5-43-AB-A2')
        assert  cipher_text == real, 'Decrypted text does not equal the real value (expected "{}", got "{}")'\
            .format(get_representation(real), get_representation(cipher_text))

if __name__ == '__main__':
    unittest.main()
