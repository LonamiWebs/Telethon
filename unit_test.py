import unittest
import socket
import threading
import random
import utils.helpers as utils

from network.tcp_client import TcpClient
from utils.binary_reader import BinaryReader
from utils.binary_writer import BinaryWriter
from utils.factorizator import Factorizator


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

if __name__ == '__main__':
    unittest.main()
