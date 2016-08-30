import unittest
import socket
import threading
import random
from time import sleep
import utils.helpers as utils

from network.tcp_client import TcpClient

from utils.binary_reader import BinaryReader
from utils.binary_writer import BinaryWriter


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



if __name__ == '__main__':
    unittest.main()
