import asyncio
import struct

from . import TLObject, GzipPacked
from ..tl.functions import InvokeAfterMsgRequest


class TLMessage(TLObject):
    """
    https://core.telegram.org/mtproto/service_messages#simple-container.

    Messages are what's ultimately sent to Telegram:
        message msg_id:long seqno:int bytes:int body:bytes = Message;

    Each message has its own unique identifier, and the body is simply
    the serialized request that should be executed on the server. Then
    Telegram will, at some point, respond with the result for this msg.

    Thus it makes sense that requests and their result are bound to a
    sent `TLMessage`, and this result can be represented as a `Future`
    that will eventually be set with either a result, error or cancelled.
    """
    def __init__(self, msg_id, seq_no, body=None, request=None, after_id=0):
        super().__init__()
        self.msg_id = msg_id
        self.seq_no = seq_no
        self.container_msg_id = None
        self.future = asyncio.Future()

        # TODO Perhaps it's possible to merge body and request?
        # We need things like rpc_result and gzip_packed to
        # be readable by the ``BinaryReader`` for such purpose.

        # Used for incoming, not-decoded messages
        self.body = body

        # Used for outgoing, not-encoded messages
        self.request = request

        # After which message ID this one should run. We do this so
        # InvokeAfterMsgRequest is transparent to the user and we can
        # easily invoke after while confirming the original request.
        self.after_id = after_id

    def to_dict(self, recursive=True):
        return {
            'msg_id': self.msg_id,
            'seq_no': self.seq_no,
            'request': self.request,
            'container_msg_id': self.container_msg_id,
            'after_id': self.after_id
        }

    def __bytes__(self):
        if self.after_id is None:
            body = GzipPacked.gzip_if_smaller(self.request)
        else:
            body = GzipPacked.gzip_if_smaller(
                InvokeAfterMsgRequest(self.after_id, self.request))

        return struct.pack('<qii', self.msg_id, self.seq_no, len(body)) + body

    def __str__(self):
        return TLObject.pretty_format(self)

    def stringify(self):
        return TLObject.pretty_format(self, indent=0)
