import gzip
import struct

from . import TLObject


class GzipPacked(TLObject):
    CONSTRUCTOR_ID = 0x3072cfa1

    def __init__(self, data):
        super().__init__()
        self.data = data

    @staticmethod
    def gzip_if_smaller(request):
        """Calls bytes(request), and based on a certain threshold,
           optionally gzips the resulting data. If the gzipped data is
           smaller than the original byte array, this is returned instead.

           Note that this only applies to content related requests.
        """
        data = bytes(request)
        # TODO This threshold could be configurable
        if request.content_related and len(data) > 512:
            gzipped = bytes(GzipPacked(data))
            return gzipped if len(gzipped) < len(data) else data
        else:
            return data

    def __bytes__(self):
        # TODO Maybe compress level could be an option
        return struct.pack('<I', GzipPacked.CONSTRUCTOR_ID) + \
               TLObject.serialize_bytes(gzip.compress(self.data))

    @staticmethod
    def read(reader):
        assert reader.read_int(signed=False) == GzipPacked.CONSTRUCTOR_ID
        return gzip.decompress(reader.tgread_bytes())
