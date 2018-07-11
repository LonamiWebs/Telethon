"""
This module contains the BinaryReader utility class.
"""
import os
from datetime import datetime, timezone
from io import BufferedReader, BytesIO
from struct import unpack

from ..errors import TypeNotFoundError
from ..tl.alltlobjects import tlobjects
from ..tl.core import core_objects


class BinaryReader:
    """
    Small utility class to read binary data.
    Also creates a "Memory Stream" if necessary
    """

    def __init__(self, data=None, stream=None):
        if data:
            self.stream = BytesIO(data)
        elif stream:
            self.stream = stream
        else:
            raise ValueError('Either bytes or a stream must be provided')

        self.reader = BufferedReader(self.stream)
        self._last = None  # Should come in handy to spot -404 errors

    # region Reading

    # "All numbers are written as little endian."
    # https://core.telegram.org/mtproto
    def read_byte(self):
        """Reads a single byte value."""
        return self.read(1)[0]

    def read_int(self, signed=True):
        """Reads an integer (4 bytes) value."""
        return int.from_bytes(self.read(4), byteorder='little', signed=signed)

    def read_long(self, signed=True):
        """Reads a long integer (8 bytes) value."""
        return int.from_bytes(self.read(8), byteorder='little', signed=signed)

    def read_float(self):
        """Reads a real floating point (4 bytes) value."""
        return unpack('<f', self.read(4))[0]

    def read_double(self):
        """Reads a real floating point (8 bytes) value."""
        return unpack('<d', self.read(8))[0]

    def read_large_int(self, bits, signed=True):
        """Reads a n-bits long integer value."""
        return int.from_bytes(
            self.read(bits // 8), byteorder='little', signed=signed)

    def read(self, length=None):
        """Read the given amount of bytes."""
        if length is None:
            return self.reader.read()

        result = self.reader.read(length)
        if len(result) != length:
            raise BufferError(
                'No more data left to read (need {}, got {}: {}); last read {}'
                .format(length, len(result), repr(result), repr(self._last))
            )

        self._last = result
        return result

    def get_bytes(self):
        """Gets the byte array representing the current buffer as a whole."""
        return self.stream.getvalue()

    # endregion

    # region Telegram custom reading

    def tgread_bytes(self):
        """
        Reads a Telegram-encoded byte array, without the need of
        specifying its length.
        """
        first_byte = self.read_byte()
        if first_byte == 254:
            length = self.read_byte() | (self.read_byte() << 8) | (
                self.read_byte() << 16)
            padding = length % 4
        else:
            length = first_byte
            padding = (length + 1) % 4

        data = self.read(length)
        if padding > 0:
            padding = 4 - padding
            self.read(padding)

        return data

    def tgread_string(self):
        """Reads a Telegram-encoded string."""
        return str(self.tgread_bytes(), encoding='utf-8', errors='replace')

    def tgread_bool(self):
        """Reads a Telegram boolean value."""
        value = self.read_int(signed=False)
        if value == 0x997275b5:  # boolTrue
            return True
        elif value == 0xbc799737:  # boolFalse
            return False
        else:
            raise RuntimeError('Invalid boolean code {}'.format(hex(value)))

    def tgread_date(self):
        """Reads and converts Unix time (used by Telegram)
           into a Python datetime object.
        """
        value = self.read_int()
        if value == 0:
            return None
        else:
            return datetime.fromtimestamp(value, tz=timezone.utc)

    def tgread_object(self):
        """Reads a Telegram object."""
        constructor_id = self.read_int(signed=False)
        clazz = tlobjects.get(constructor_id, None)
        if clazz is None:
            # The class was None, but there's still a
            # chance of it being a manually parsed value like bool!
            value = constructor_id
            if value == 0x997275b5:  # boolTrue
                return True
            elif value == 0xbc799737:  # boolFalse
                return False
            elif value == 0x1cb5c415:  # Vector
                return [self.tgread_object() for _ in range(self.read_int())]

            clazz = core_objects.get(constructor_id, None)
            if clazz is None:
                # If there was still no luck, give up
                self.seek(-4)  # Go back
                pos = self.tell_position()
                error = TypeNotFoundError(constructor_id, self.read())
                self.set_position(pos)
                raise error

        return clazz.from_reader(self)

    def tgread_vector(self):
        """Reads a vector (a list) of Telegram objects."""
        if 0x1cb5c415 != self.read_int(signed=False):
            raise RuntimeError('Invalid constructor code, vector was expected')

        count = self.read_int()
        return [self.tgread_object() for _ in range(count)]

    # endregion

    def close(self):
        """Closes the reader, freeing the BytesIO stream."""
        self.reader.close()

    # region Position related

    def tell_position(self):
        """Tells the current position on the stream."""
        return self.reader.tell()

    def set_position(self, position):
        """Sets the current position on the stream."""
        self.reader.seek(position)

    def seek(self, offset):
        """
        Seeks the stream position given an offset from the current position.
        The offset may be negative.
        """
        self.reader.seek(offset, os.SEEK_CUR)

    # endregion

    # region with block

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    # endregion
