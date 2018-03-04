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
        self.container_msg_id = None

    def to_dict(self, recursive=True):
        return {
            'msg_id': self.msg_id,
            'seq_no': self.seq_no,
            'request': self.request,
            'container_msg_id': self.container_msg_id,
        }

    def __bytes__(self):
        body = GzipPacked.gzip_if_smaller(self.request)
        return struct.pack('<qii', self.msg_id, self.seq_no, len(body)) + body

    def __str__(self):
        return TLObject.pretty_format(self)

    def stringify(self):
        return TLObject.pretty_format(self, indent=0)
