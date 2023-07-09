import struct


class Request(bytes):
    __slots__ = ()

    @property
    def constructor_id(self) -> int:
        try:
            cid = struct.unpack("<i", self[:4])[0]
            assert isinstance(cid, int)
            return cid
        except struct.error:
            return 0

    def debug_name(self) -> str:
        return f"request#{self.constructor_id:x}"
