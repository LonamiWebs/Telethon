import gzip

from . import TLObject
from ..extensions import BinaryWriter


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
        with BinaryWriter() as writer:
            writer.write_int(GzipPacked.constructor_id, signed=False)
            writer.tgwrite_bytes(gzip.compress(self.data))
            return writer.get_bytes()

    @staticmethod
    def read(reader):
        reader.read_int(signed=False)  # code
        return gzip.decompress(reader.tgread_bytes())
