import struct

from . import TLObject, GzipPacked


class TLMessage(TLObject):
    """https://core.telegram.org/mtproto/service_messages#simple-container"""
    def __init__(self, session, request):
        super().__init__()
        del self.content_related
        self.msg_id = session.get_new_msg_id()
        self.seq_no = session.generate_sequence(request.content_related)
        self.request = request

    def to_bytes(self):
        body = GzipPacked.gzip_if_smaller(self.request)
        return struct.pack('<qii', self.msg_id, self.seq_no, len(body)) + body
