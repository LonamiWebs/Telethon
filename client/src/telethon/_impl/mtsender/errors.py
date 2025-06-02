import io

from ..mtproto.mtp.types import DeserializationError
from ..mtproto.transport.abcs import TransportError

ReadError = io.BlockingIOError | TransportError | DeserializationError


class IOError(io.BlockingIOError):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)
