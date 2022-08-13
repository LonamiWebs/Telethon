"""
This module holds core "special" types, which are more convenient ways
to do stuff in a `telethon.network.mtprotosender.MTProtoSender` instance.

Only special cases are gzip-packed data, the response message (not a
client message), the message container which references these messages
and would otherwise conflict with the rest, and finally the RpcResult:

    rpc_result#f35c6d01 req_msg_id:long result:bytes = RpcResult;

Three things to note with this definition:
1. The constructor ID is actually ``42d36c2c``.
2. Those bytes are not read like the rest of bytes (length + payload).
   They are actually the raw bytes of another object, which can't be
   read directly because it depends on per-request information (since
   some can return ``Vector<int>`` and ``Vector<long>``).
3. Those bytes may be gzipped data, which needs to be treated early.
"""
from .tlmessage import TLMessage
from .gzippacked import GzipPacked
from .messagecontainer import MessageContainer
from .rpcresult import RpcResult

core_objects = {x.CONSTRUCTOR_ID: x for x in (
    GzipPacked, MessageContainer, RpcResult
)}
