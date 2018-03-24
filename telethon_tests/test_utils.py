import os
import unittest
from telethon.tl import TLObject
from telethon.extensions import BinaryReader


class UtilsTests(unittest.TestCase):
    def test_binary_writer_reader(self):
        # Test that we can read properly
        data = b'\x01\x05\x00\x00\x00\r\x00\x00\x00\x00\x00\x00\x00\x00\x00' \
               b'\x88A\x00\x00\x00\x00\x00\x009@\x1a\x1b\x1c\x1d\x1e\x1f ' \
               b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00' \
               b'\x00\x80'

        with BinaryReader(data) as reader:
            value = reader.read_byte()
            self.assertEqual(value, 1,
                             msg='Example byte should be 1 but is {}'.format(value))

            value = reader.read_int()
            self.assertEqual(value, 5,
                             msg='Example integer should be 5 but is {}'.format(value))

            value = reader.read_long()
            self.assertEqual(value, 13,
                             msg='Example long integer should be 13 but is {}'.format(value))

            value = reader.read_float()
            self.assertEqual(value, 17.0,
                             msg='Example float should be 17.0 but is {}'.format(value))

            value = reader.read_double()
            self.assertEqual(value, 25.0,
                             msg='Example double should be 25.0 but is {}'.format(value))

            value = reader.read(7)
            self.assertEqual(value, bytes([26, 27, 28, 29, 30, 31, 32]),
                             msg='Example bytes should be {} but is {}'
                             .format(bytes([26, 27, 28, 29, 30, 31, 32]), value))

            value = reader.read_large_int(128, signed=False)
            self.assertEqual(value, 2**127,
                             msg='Example large integer should be {} but is {}'.format(2**127, value))

    def test_binary_tgwriter_tgreader(self):
        small_data = os.urandom(33)
        small_data_padded = os.urandom(19)  # +1 byte for length = 20 (%4 = 0)

        large_data = os.urandom(999)
        large_data_padded = os.urandom(1024)

        data = (small_data, small_data_padded, large_data, large_data_padded)
        string = 'Testing Telegram strings, this should work properly!'
        serialized = b''.join(TLObject.serialize_bytes(d) for d in data) + \
                     TLObject.serialize_bytes(string)

        with BinaryReader(serialized) as reader:
            # And then try reading it without errors (it should be unharmed!)
            for datum in data:
                value = reader.tgread_bytes()
                self.assertEqual(value, datum,
                                 msg='Example bytes should be {} but is {}'.format(datum, value))

            value = reader.tgread_string()
            self.assertEqual(value, string,
                             msg='Example string should be {} but is {}'.format(string, value))
