import struct


class Request:
    __slots__ = "_body"

    def __init__(self, body: bytes):
        self._body = body

    @property
    def constructor_id(self) -> int:
        try:
            cid = struct.unpack("<i", self._body[:4])[0]
            assert isinstance(cid, int)
            return cid
        except struct.error:
            return 0

    def debug_name(self) -> str:
        return f"request#{self.constructor_id:x}"
