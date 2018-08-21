import asyncio
import logging
import struct

from .gzippacked import GzipPacked
from .. import TLObject
from ..functions import InvokeAfterMsgRequest

__log__ = logging.getLogger(__name__)


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
    def __init__(self, msg_id, seq_no, obj, *, loop, out=False, after_id=0):
        self.obj = obj
        self.container_msg_id = None

        # If no loop is given then it is an incoming message.
        # Only outgoing messages need the future to await them.
        self.future = loop.create_future() if loop else None

        # After which message ID this one should run. We do this so
        # InvokeAfterMsgRequest is transparent to the user and we can
        # easily invoke after while confirming the original request.
        # TODO Currently we don't update this if another message ID changes
        self.after_id = after_id

        # There are two use-cases for the TLMessage, outgoing and incoming.
        # Outgoing messages are meant to be serialized and sent across the
        # network so it makes sense to pack them as early as possible and
        # avoid this computation if it needs to be resent, and also shows
        # serializing-errors as early as possible (foreground task).
        #
        # We assume obj won't change so caching the bytes is safe to do.
        # Caching bytes lets us get the size in a fast way, necessary for
        # knowing whether a container can be sent (<1MB) or not (too big).
        #
        # Incoming messages don't really need this body, but we save the
        # msg_id and seq_no inside the body for consistency and raise if
        # one tries to bytes()-ify the entire message (len == 12).
        if not out:
            self._body = struct.pack('<qi', msg_id, seq_no)
        else:
            try:
                if self.after_id is None:
                    body = GzipPacked.gzip_if_smaller(self.obj)
                else:
                    body = GzipPacked.gzip_if_smaller(
                        InvokeAfterMsgRequest(self.after_id, self.obj))
            except Exception:
                # struct.pack doesn't give a lot of information about
                # why it may fail so log the exception AND the object
                __log__.exception('Failed to pack %s', self.obj)
                raise

            self._body = struct.pack('<qii', msg_id, seq_no, len(body)) + body

    def to_dict(self):
        return {
            '_': 'TLMessage',
            'msg_id': self.msg_id,
            'seq_no': self.seq_no,
            'obj': self.obj,
            'container_msg_id': self.container_msg_id
        }

    @property
    def msg_id(self):
        return struct.unpack('<q', self._body[:8])[0]

    @msg_id.setter
    def msg_id(self, value):
        self._body = struct.pack('<q', value) + self._body[8:]

    @property
    def seq_no(self):
        return struct.unpack('<i', self._body[8:12])[0]

    def __bytes__(self):
        if len(self._body) == 12:  # msg_id, seqno
            raise TypeError('Incoming messages should not be bytes()-ed')

        return self._body

    def size(self):
        return len(self._body)
