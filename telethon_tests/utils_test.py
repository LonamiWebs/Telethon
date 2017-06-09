import os
import unittest
from telethon.extensions import BinaryReader, BinaryWriter


class UtilsTests(unittest.TestCase):
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
            expected = b'\x01\x05\x00\x00\x00\r\x00\x00\x00\x00\x00\x00\x00\x00\x00\x88A\x00\x00\x00\x00\x00\x00' \
                       b'9@\x1a\x1b\x1c\x1d\x1e\x1f \x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x80'

            assert data == expected, 'Retrieved data does not match the expected value'

        with BinaryReader(data) as reader:
            value = reader.read_byte()
            assert value == 1, 'Example byte should be 1 but is {}'.format(
                value)

            value = reader.read_int()
            assert value == 5, 'Example integer should be 5 but is {}'.format(
                value)

            value = reader.read_long()
            assert value == 13, 'Example long integer should be 13 but is {}'.format(
                value)

            value = reader.read_float()
            assert value == 17.0, 'Example float should be 17.0 but is {}'.format(
                value)

            value = reader.read_double()
            assert value == 25.0, 'Example double should be 25.0 but is {}'.format(
                value)

            value = reader.read(7)
            assert value == bytes([26, 27, 28, 29, 30, 31, 32]), 'Example bytes should be {} but is {}' \
                .format(bytes([26, 27, 28, 29, 30, 31, 32]), value)

            value = reader.read_large_int(128, signed=False)
            assert value == 2**127, 'Example large integer should be {} but is {}'.format(
                2**127, value)

        # Test Telegram that types are written right
        with BinaryWriter() as writer:
            writer.write_int(0x60469778)
            buffer = writer.get_bytes()
            valid = b'\x78\x97\x46\x60'  # Tested written bytes using C#'s MemoryStream

            assert buffer == valid, 'Written type should be {} but is {}'.format(
                list(valid), list(buffer))

    @staticmethod
    def test_binary_tgwriter_tgreader():
        small_data = os.urandom(33)
        small_data_padded = os.urandom(
            19)  # +1 byte for length = 20 (evenly divisible by 4)

        large_data = os.urandom(999)
        large_data_padded = os.urandom(1024)

        data = (small_data, small_data_padded, large_data, large_data_padded)
        string = 'Testing Telegram strings, this should work properly!'

        with BinaryWriter() as writer:
            # First write the data
            for datum in data:
                writer.tgwrite_bytes(datum)
            writer.tgwrite_string(string)

            with BinaryReader(writer.get_bytes()) as reader:
                # And then try reading it without errors (it should be unharmed!)
                for datum in data:
                    value = reader.tgread_bytes()
                    assert value == datum, 'Example bytes should be {} but is {}'.format(
                        datum, value)

                value = reader.tgread_string()
                assert value == string, 'Example string should be {} but is {}'.format(
                    string, value)
