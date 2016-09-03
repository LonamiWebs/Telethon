import unittest
import socket
import threading
import random
import utils.helpers as utils

from network.tcp_client import TcpClient
from utils.binary_reader import BinaryReader
from utils.binary_writer import BinaryWriter
from utils.factorizator import Factorizator
from utils.rsa import RSA


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
    def test_rsa():
        fingerprint = '216BE86C022BB4C3'
        data = get_bytes('EC-5A-C9-83-08-29-86-64-72-35-B8-4B-7D-00-00-00-04-59-6B-F5-41-00-00-00-04-76-E1-1B-3D-00-00-00-CE-2A-EA-DE-D2-17-35-B8-E6-AB-3B-3A-00-0A-79-46-C6-09-3A-99-E9-C1-5B-B5-20-30-27-B7-D5-4F-2F-A3-1C-AF-F4-23-54-B2-5E-BD-00-AB-71-0A-3E-67-94-21-E3-B3-72-71-C0-29-50-00-19-8C-CD-6A-52-D4-CE-9E')
        hashsum = utils.sha1(data)
        real = get_bytes('6C-86-F7-6D-A2-F5-C2-A5-D0-4D-D5-45-8A-85-AE-62-8B-F7-84-A0')

        assert hashsum == real, 'Invalid sha1 hashsum representation (should be {}, but is {})'\
            .format(get_representation(real), get_representation(data))

        with BinaryWriter() as writer:
            writer.write(hashsum)
            writer.write(data)

            real = get_bytes('6C-86-F7-6D-A2-F5-C2-A5-D0-4D-D5-45-8A-85-AE-62-8B-F7-84-A0-EC-5A-C9-83-08-29-86-64-72-35-B8-4B-7D-00-00-00-04-59-6B-F5-41-00-00-00-04-76-E1-1B-3D-00-00-00-CE-2A-EA-DE-D2-17-35-B8-E6-AB-3B-3A-00-0A-79-46-C6-09-3A-99-E9-C1-5B-B5-20-30-27-B7-D5-4F-2F-A3-1C-AF-F4-23-54-B2-5E-BD-00-AB-71-0A-3E-67-94-21-E3-B3-72-71-C0-29-50-00-19-8C-CD-6A-52-D4-CE-9E')
            assert writer.get_bytes() == real, 'Invalid written value'

        # Since the random padding is random by nature, use the sample data we know the result for
        data = get_bytes(
            '6C-86-F7-6D-A2-F5-C2-A5-D0-4D-D5-45-8A-85-AE-62-8B-F7-84-A0-EC-5A-C9-83-08-29-86-64-72-35-B8-4B-7D-00-00-00-04-59-6B-F5-41-00-00-00-04-76-E1-1B-3D-00-00-00-CE-2A-EA-DE-D2-17-35-B8-E6-AB-3B-3A-00-0A-79-46-C6-09-3A-99-E9-C1-5B-B5-20-30-27-B7-D5-4F-2F-A3-1C-AF-F4-23-54-B2-5E-BD-00-AB-71-0A-3E-67-94-21-E3-B3-72-71-C0-29-50-00-19-8C-CD-6A-52-D4-CE-9E-10-F4-6E-C6-1F-CB-DC-8C-2A-7A-91-92-71-22-D6-08-AD-B4-6D-5F-D3-59-0F-F4-71-1A-57-FF-17-9E-AE-CD-D8-90-4B-DB-1A-1F-06-C1-22-8D-20-67-F8-F0-F2-D1-26-DF-E9-78-72-A7-DF-B6-E5-7A-55-04-73-DD-74-8B-CB-C3-B9-E1-D7-FA-EE-8E-AD-AB-3D-46-39-A8-FB-80-28-85-D8-38-B5-35-5B-30-B0-94-F6-A0-CA-02-4E-45-18-94-9B-35-36-11-FA-2C-F0-5B-CA-C6-6A-98-7D-3C-7E-D4-DB-ED-05-3C-D6-95-68-88-30-43-04-4E-C3-AB-5D-F7-2D-A5-0C-C6-49-17-8B-AC-48')

        e = 65537
        m = 24403446649145068056824081744112065346446136066297307473868293895086332508101251964919587745984311372853053253457835208829824428441874946556659953519213382748319518214765985662663680818277989736779506318868003755216402538945900388706898101286548187286716959100102939636333452457308619454821845196109544157601096359148241435922125602449263164512290854366930013825808102403072317738266383237191313714482187326643144603633877219028262697593882410403273959074350849923041765639673335775605842311578109726403165298875058941765362622936097839775380070572921007586266115476975819175319995527916042178582540628652481530373407

        cipher_text = utils.get_byte_array(pow(int.from_bytes(data, byteorder='big'), e, m), signed=False)
        real = get_bytes('13-8A-DC-F1-10-FF-59-29-2D-ED-4A-16-AA-D9-FA-15-A5-9A-A2-A6-33-D0-23-77-6F-E7-42-30-52-9E-4E-A9-CA-8F-CD-11-71-AB-C8-E2-97-2C-B9-A1-68-FA-4D-02-A9-56-30-84-5B-F6-5F-5D-1E-95-53-A4-A9-8F-1F-66-82-0C-20-8F-6D-EB-6F-B0-F5-D2-6C-45-89-14-1F-69-85-C8-6F-C7-41-A5-76-5F-F5-BA-9B-18-32-F7-02-C8-29-A7-70-BE-8E-FD-9E-86-48-6D-00-1E-AF-77-3F-7C-A4-1E-CD-03-21-18-4A-4D-57-FB-D9-6F-B0-4A-AD-24-A4-6F-01-07-CB-56-AC-37-22-9F-50-1F-EA-B9-17-51-EB-4B-A9-30-14-5A-A8-A9-5F-9D-9D-A5-AE-46-86-0D-0B-07-2D-84-C6-3B-DD-AD-4B-EA-89-07-CF-6B-DD-D4-68-38-F9-A9-62-A7-A3-3A-CB-79-F3-42-1B-28-E4-25-90-9B-B2-ED-EE-BC-65-8B-10-21-38-27-8B-66-98-51-A2-30-4B-F0-EA-BD-5D-E1-7D-D0-55-6E-A5-D1-FB-12-01-C2-44-D7-1F-B5-28-37-3B-08-8D-3B-79-59-D6-15-76-A4-4B-E6-3C-B3-16-58-88-9F-F9-77-21-C1-99-4E')
        assert cipher_text == real, 'Invalid ciphered text (should be {}, but is {})'\
            .format(get_representation(real), get_representation(cipher_text))


if __name__ == '__main__':
    unittest.main()
