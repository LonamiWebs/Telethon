import asyncio
from ..mtproto import (
    MissingBytesError,
    Transport,
)

MAXIMUM_DATA = (1024 * 1024) + (8 * 1024)


class BufferedTransportProtocol(asyncio.BufferedProtocol):
    __slots__ = (
        "_transport",
        "_buffer",
        "_buffer_head",
        "_packets",
        "_output",
        "_closed",
    )

    def __init__(self, transport: Transport):
        self._transport = transport
        self._buffer = bytearray(MAXIMUM_DATA)
        self._buffer_head = 0
        self._packets: asyncio.Queue[bytes] = asyncio.Queue()
        self._output = bytearray()
        self._closed = asyncio.Event()

    # Method overrides

    def get_buffer(self, sizehint):
        return self._buffer

    def buffer_updated(self, nbytes):
        self._buffer_head += nbytes
        while self._buffer_head:
            self._output.clear()
            try:
                n = self._transport.unpack(
                    memoryview(self._buffer)[: self._buffer_head], self._output
                )
            except MissingBytesError as e:
                print(e)
                return
            else:
                del self._buffer[:n]
                self._buffer += bytes(n)
                self._buffer_head -= n
                self._packets.put_nowait(bytes(self._output))

    def connection_lost(self, exc):
        self._closed.set()

    # Custom methods

    def wait_closed(self):
        return self._closed.wait()

    def wait_packet(self):
        return self._packets.get()
