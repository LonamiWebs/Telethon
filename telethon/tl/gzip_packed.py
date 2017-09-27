import gzip
import struct

from . import TLObject


class GzipPacked(TLObject):
    constructor_id = 0x3072cfa1

    def __init__(self, data):
        super().__init__()
        self.data = data

    @staticmethod
    def gzip_if_smaller(request):
        """Calls request.to_bytes(), and based on a certain threshold,
           optionally gzips the resulting data. If the gzipped data is
           smaller than the original byte array, this is returned instead.

           Note that this only applies to content related requests.
        """
        data = request.to_bytes()
        # TODO This threshold could be configurable
        if request.content_related and len(data) > 512:
            gzipped = GzipPacked(data).to_bytes()
            return gzipped if len(gzipped) < len(data) else data
        else:
            return data

    def to_bytes(self):
        # TODO Maybe compress level could be an option
        return struct.pack('<I', GzipPacked.constructor_id) + \
               TLObject.serialize_bytes(gzip.compress(self.data))

    @staticmethod
    def read(reader):
        reader.read_int(signed=False)  # code
        return gzip.decompress(reader.tgread_bytes())
