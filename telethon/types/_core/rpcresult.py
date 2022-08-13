from .gzippacked import GzipPacked
from ..._misc.tlobject import TLObject
from ... import _tl


class RpcResult(TLObject):
    CONSTRUCTOR_ID = 0xf35c6d01

    def __init__(self, req_msg_id, body, error):
        self.req_msg_id = req_msg_id
        self.body = body
        self.error = error

    @classmethod
    def _from_reader(cls, reader):
        msg_id = reader.read_long()
        inner_code = reader.read_int(signed=False)
        if inner_code == _tl.RpcError.CONSTRUCTOR_ID:
            return RpcResult(msg_id, None, _tl.RpcError._from_reader(reader))
        if inner_code == GzipPacked.CONSTRUCTOR_ID:
            return RpcResult(msg_id, GzipPacked._from_reader(reader).data, None)

        reader.seek(-4)
        # This reader.read() will read more than necessary, but it's okay.
        # We could make use of MessageContainer's length here, but since
        # it's not necessary we don't need to care about it.
        return RpcResult(msg_id, reader.read(), None)

    def to_dict(self):
        return {
            '_': 'RpcResult',
            'req_msg_id': self.req_msg_id,
            'body': self.body,
            'error': self.error
        }
