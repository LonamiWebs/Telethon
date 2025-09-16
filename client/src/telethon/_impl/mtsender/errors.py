from struct import error as struct_error

from ..mtproto.mtp.types import DeserializationError
from ..mtproto.transport.abcs import TransportError

ReadError = struct_error | TransportError | DeserializationError
