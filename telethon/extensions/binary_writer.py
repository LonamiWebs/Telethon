from io import BufferedWriter, BytesIO
from struct import pack


class BinaryWriter:
    """
    Small utility class to write binary data.
    Also creates a "Memory Stream" if necessary
    """

    def __init__(self, stream=None):
        if not stream:
            stream = BytesIO()

        self.writer = BufferedWriter(stream)
        self.written_count = 0

    # region Writing

    # "All numbers are written as little endian." |> Source: https://core.telegram.org/mtproto
    def write_byte(self, value):
        """Writes a single byte value"""
        self.writer.write(pack('B', value))
        self.written_count += 1

    def write_int(self, value, signed=True):
        """Writes an integer value (4 bytes), which can or cannot be signed"""
        self.writer.write(
            int.to_bytes(
                value, length=4, byteorder='little', signed=signed))
        self.written_count += 4

    def write_long(self, value, signed=True):
        """Writes a long integer value (8 bytes), which can or cannot be signed"""
        self.writer.write(
            int.to_bytes(
                value, length=8, byteorder='little', signed=signed))
        self.written_count += 8

    def write_float(self, value):
        """Writes a floating point value (4 bytes)"""
        self.writer.write(pack('<f', value))
        self.written_count += 4

    def write_double(self, value):
        """Writes a floating point value (8 bytes)"""
        self.writer.write(pack('<d', value))
        self.written_count += 8

    def write_large_int(self, value, bits, signed=True):
        """Writes a n-bits long integer value"""
        self.writer.write(
            int.to_bytes(
                value, length=bits // 8, byteorder='little', signed=signed))
        self.written_count += bits // 8

    def write(self, data):
        """Writes the given bytes array"""
        self.writer.write(data)
        self.written_count += len(data)

    # endregion

    # region Telegram custom writing

    def tgwrite_bytes(self, data):
        """Write bytes by using Telegram guidelines"""
        if len(data) < 254:
            padding = (len(data) + 1) % 4
            if padding != 0:
                padding = 4 - padding

            self.write(bytes([len(data)]))
            self.write(data)

        else:
            padding = len(data) % 4
            if padding != 0:
                padding = 4 - padding

            self.write(bytes([254]))
            self.write(bytes([len(data) % 256]))
            self.write(bytes([(len(data) >> 8) % 256]))
            self.write(bytes([(len(data) >> 16) % 256]))
            self.write(data)

        self.write(bytes(padding))

    def tgwrite_string(self, string):
        """Write a string by using Telegram guidelines"""
        self.tgwrite_bytes(string.encode('utf-8'))

    def tgwrite_bool(self, boolean):
        """Write a boolean value by using Telegram guidelines"""
        #                     boolTrue                boolFalse
        self.write_int(0x997275b5 if boolean else 0xbc799737, signed=False)

    def tgwrite_date(self, datetime):
        """Converts a Python datetime object into Unix time (used by Telegram) and writes it"""
        value = 0 if datetime is None else int(datetime.timestamp())
        self.write_int(value)

    def tgwrite_object(self, tlobject):
        """Writes a Telegram object"""
        tlobject.on_send(self)

    def tgwrite_vector(self, vector):
        """Writes a vector of Telegram objects"""
        self.write_int(0x1cb5c415, signed=False)  # Vector's constructor ID
        self.write_int(len(vector))
        for item in vector:
            self.tgwrite_object(item)

    # endregion

    def flush(self):
        """Flush the current stream to "update" changes"""
        self.writer.flush()

    def close(self):
        """Close the current stream"""
        self.writer.close()

    def get_bytes(self, flush=True):
        """Get the current bytes array content from the buffer, optionally flushing first"""
        if flush:
            self.writer.flush()
        return self.writer.raw.getvalue()

    def get_written_bytes_count(self):
        """Gets the count of bytes written in the buffer.
           This may NOT be equal to the stream length if one was provided when initializing the writer"""
        return self.written_count

    # with block
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
