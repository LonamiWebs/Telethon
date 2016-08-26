from io import BytesIO, BufferedWriter
from struct import pack


class BinaryWriter:
    """
    Small utility class to write binary data.
    Also creates a "Memory Stream" if necessary
    """

    def __init__(self, stream=None):
        if not stream:
            stream = BytesIO()

        self.stream = stream
        self.writer = BufferedWriter(self.stream)

    # region Writing

    def write_byte(self, byte):
        self.writer.write(pack('B', byte))

    def write_int(self, integer, signed=True):
        if not signed:
            integer &= 0xFFFFFFFF  # Ensure it's unsigned (see http://stackoverflow.com/a/30092291/4759433)
        self.writer.write(pack('I', integer))

    def write_long(self, long, signed=True):
        if not signed:
            long &= 0xFFFFFFFFFFFFFFFF
        self.writer.write(pack('Q', long))

    def write(self, data):
        self.writer.write(data)

    # endregion

    # region Telegram custom writing

    def tgwrite_bytes(self, data):

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

            # TODO ensure that _this_ is right (it appears to be)
            self.write(bytes([254]))
            self.write(bytes([len(data) % 256]))
            self.write(bytes([(len(data) >> 8) % 256]))
            self.write(bytes([(len(data) >> 16) % 256]))
            self.write(data)

            """ Original:
                    binaryWriter.Write((byte)254);
                    binaryWriter.Write((byte)(bytes.Length));
                    binaryWriter.Write((byte)(bytes.Length >> 8));
                    binaryWriter.Write((byte)(bytes.Length >> 16));
            """

        self.write(bytes(padding))

    def tgwrite_string(self, string):
        return self.tgwrite_bytes(string.encode('utf-8'))

    # endregion

    def flush(self):
        self.writer.flush()

    def close(self):
        self.writer.close()
        # TODO Do I need to close the underlying stream?

    def get_bytes(self, flush=True):
        if flush:
            self.writer.flush()
        self.stream.getbuffer()

    # with block
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
