from io import BytesIO, BufferedReader
from tl.all_tlobjects import tlobjects
import os


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
            raise ValueError("Either bytes or a stream must be provided")

        self.reader = BufferedReader(self.stream)

    # region Reading

    def read_int(self, signed=True):
        return int.from_bytes(self.reader.read(4), signed=signed, byteorder='big')

    def read_long(self, signed=True):
        return int.from_bytes(self.reader.read(8), signed=signed, byteorder='big')

    def read_large_int(self, bits):
        return int.from_bytes(self.reader.read(bits // 8), byteorder='big')

    def read(self, length):
        return self.reader.read(length)

    def get_bytes(self):
        return self.stream.getbuffer()

    # endregion

    # region Telegram custom reading

    def tgread_bytes(self):
        first_byte = self.read(1)
        if first_byte == 254:
            length = self.read(1) | (self.read(1) << 8) | (self.read(1) << 16)
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
        return str(self.tgread_bytes(), encoding='utf-8')

    def tgread_object(self):
        """Reads a Telegram object"""
        id = self.read_int()
        clazz = tlobjects.get(id, None)
        if clazz is None:
            raise ImportError('Could not find a matching ID for the TLObject that was supposed to be read. '
                              'Found ID: {}'.format(hex(id)))

        # Instantiate the class and return the result
        result = clazz()
        result.on_response(self)
        return result

    # endregion

    def close(self):
        self.reader.close()
        # TODO Do I need to close the underlying stream?

    # region Position related

    def tell_position(self):
        """Tells the current position on the stream"""
        return self.reader.tell()

    def set_position(self, position):
        """Sets the current position on the stream"""
        self.reader.seek(position)

    def seek(self, offset):
        """Seeks the stream position given an offset from the current position. May be negative"""
        self.reader.seek(offset, os.SEEK_CUR)

    # endregion

    # region with block

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    # endregion
