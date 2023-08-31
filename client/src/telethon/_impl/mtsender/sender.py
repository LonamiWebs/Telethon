import asyncio
import struct
import time
from abc import ABC
from asyncio import FIRST_COMPLETED, Future, Queue, StreamReader, StreamWriter
from dataclasses import dataclass
from typing import BinaryIO, Generic, List, Optional, Self, Tuple, TypeVar

from ..crypto.auth_key import AuthKey
from ..mtproto import authentication
from ..mtproto.mtp.encrypted import Encrypted
from ..mtproto.mtp.plain import Plain
from ..mtproto.mtp.types import MsgId, Mtp
from ..mtproto.transport.abcs import MissingBytes, Transport
from ..tl.abcs import Updates
from ..tl.core.request import Request as RemoteCall
from ..tl.mtproto.functions import ping_delay_disconnect

MAXIMUM_DATA = (1024 * 1024) + (8 * 1024)

PING_DELAY = 60

NO_PING_DISCONNECT = 75

assert NO_PING_DISCONNECT > PING_DELAY


_last_id = 0


def generate_random_id() -> int:
    global _last_id
    if _last_id == 0:
        _last_id = int(time.time() * 0x100000000)
    _last_id += 1
    return _last_id


class RequestState(ABC):
    pass


class NotSerialized(RequestState):
    pass


class Serialized(RequestState):
    __slots__ = ("msg_id",)

    def __init__(self, msg_id: MsgId):
        self.msg_id = msg_id


class Sent(RequestState):
    __slots__ = ("msg_id",)

    def __init__(self, msg_id: MsgId):
        self.msg_id = msg_id


Return = TypeVar("Return")


@dataclass
class Request(Generic[Return]):
    body: bytes
    state: RequestState
    result: Future[Return]


class Enqueuer:
    __slots__ = ("_queue",)

    def __init__(self, queue: Queue[Request[object]]) -> None:
        self._queue = queue

    def enqueue(self, request: RemoteCall[Return]) -> Future[Return]:
        body = bytes(request)
        assert len(body) >= 4
        oneshot = asyncio.get_running_loop().create_future()
        self._queue.put_nowait(
            Request(body=body, state=NotSerialized(), result=oneshot)
        )
        return oneshot


@dataclass
class Sender:
    _reader: StreamReader
    _writer: StreamWriter
    _transport: Transport
    _mtp: Mtp
    _mtp_buffer: bytearray
    _requests: List[Request[object]]
    _request_rx: Queue[Request[object]]
    _next_ping: float
    _read_buffer: bytearray
    _write_drain_pending: bool

    @classmethod
    async def connect(
        cls, transport: Transport, mtp: Mtp, addr: str
    ) -> Tuple[Self, Enqueuer]:
        reader, writer = await asyncio.open_connection(*addr.split(":"))
        request_queue: Queue[object] = Queue()

        return (
            cls(
                _reader=reader,
                _writer=writer,
                _transport=transport,
                _mtp=mtp,
                _mtp_buffer=bytearray(),
                _requests=[],
                _request_rx=request_queue,
                _next_ping=asyncio.get_running_loop().time() + PING_DELAY,
                _read_buffer=bytearray(),
                _write_drain_pending=False,
            ),
            Enqueuer(request_queue),
        )

    async def invoke(self, request: RemoteCall[Return]) -> bytes:
        rx = self._enqueue_body(bytes(request))
        return await self._step_until_receive(rx)

    async def send(self, body: bytes) -> bytes:
        rx = self._enqueue_body(body)
        return await self._step_until_receive(rx)

    def _enqueue_body(self, body: bytes) -> Future[object]:
        oneshot = asyncio.get_running_loop().create_future()
        self._requests.append(Request(body=body, state=NotSerialized(), result=oneshot))
        return oneshot

    async def _step_until_receive(self, rx: Future[object]) -> bytes:
        while True:
            await self.step()
            if rx.done():
                return rx.result()

    async def step(self) -> List[Updates]:
        self._try_fill_write()

        recv_req = asyncio.create_task(self._request_rx.get())
        recv_data = asyncio.create_task(self._reader.read(MAXIMUM_DATA))
        send_data = asyncio.create_task(self._do_send())
        done, pending = await asyncio.wait(
            (recv_req, recv_data, send_data),
            timeout=self._next_ping - asyncio.get_running_loop().time(),
            return_when=FIRST_COMPLETED,
        )

        for task in pending:
            task.cancel()
        await asyncio.wait(pending)

        result = []
        if recv_req in done:
            self._requests.append(recv_req.result())
        if recv_data in done:
            result = self._on_net_read(recv_data.result())
        if send_data in done:
            self._on_net_write()
        if not done:
            self._on_ping_timeout()
        return result

    async def _do_send(self) -> None:
        if self._write_drain_pending:
            await self._writer.drain()
            self._write_drain_pending = False
        else:
            # Never return
            await asyncio.get_running_loop().create_future()

    def _try_fill_write(self) -> None:
        if self._write_drain_pending:
            return

        # TODO test that the a request is only ever sent onrece
        requests = [r for r in self._requests if isinstance(r.state, NotSerialized)]
        if not requests:
            return

        msg_ids = []
        for request in requests:
            if (msg_id := self._mtp.push(request.body)) is not None:
                msg_ids.append(msg_id)
            else:
                break

        mtp_buffer = self._mtp.finalize()
        self._transport.pack(mtp_buffer, self._writer.write)
        self._write_drain_pending = True

        for req, msg_id in zip(requests, msg_ids):
            req.state = Serialized(msg_id)

    def _on_net_read(self, read_buffer: bytes) -> List[Updates]:
        if not read_buffer:
            raise ConnectionResetError("read 0 bytes")

        self._read_buffer += read_buffer

        updates = []
        while self._read_buffer:
            self._mtp_buffer.clear()
            try:
                n = self._transport.unpack(self._read_buffer, self._mtp_buffer)
            except MissingBytes:
                break
            else:
                del self._read_buffer[:n]
                self._process_mtp_buffer(updates)

        return updates

    def _on_net_write(self) -> None:
        for req in self._requests:
            if isinstance(req.state, Serialized):
                req.state = Sent(req.state.msg_id)

    def _on_ping_timeout(self) -> None:
        ping_id = generate_random_id()
        self._enqueue_body(
            bytes(
                ping_delay_disconnect(
                    ping_id=ping_id, disconnect_delay=NO_PING_DISCONNECT
                )
            )
        )
        self._next_ping = time.time() + PING_DELAY

    def _process_mtp_buffer(self, updates: List[Updates]) -> None:
        result = self._mtp.deserialize(self._mtp_buffer)

        for update in result.updates:
            try:
                u = Updates.from_bytes(update)
            except ValueError:
                pass  # TODO log
            else:
                updates.append(u)

        for msg_id, ret in result.rpc_results:
            found = False
            for i in reversed(range(len(self._requests))):
                req = self._requests[i]
                if isinstance(req.state, Serialized) and req.state.msg_id == msg_id:
                    raise RuntimeError("got rpc result for unsent request")
                if isinstance(req.state, Sent) and req.state.msg_id == msg_id:
                    found = True
                    if isinstance(ret, bytes):
                        assert len(ret) >= 4
                    elif isinstance(ret, Exception):
                        raise NotImplementedError
                    elif isinstance(ret, RpcError):
                        ret.caused_by = req.body[:4]
                        raise ret
                    elif isinstance(ret, Dropped):
                        raise ret
                    elif isinstance(ret, Deserialize):
                        raise ret
                    elif isinstance(ret, BadMessage):
                        # TODO test that we resend the request
                        req.state = NotSerialized()
                        break
                    else:
                        raise RuntimeError("unexpected case")

                    req = self._requests.pop(i)
                    req.result.set_result(ret)
                    break
            if not found:
                pass  # TODO log

    @property
    def auth_key(self) -> Optional[bytes]:
        if isinstance(self._mtp, Encrypted):
            return self._mtp.auth_key


async def connect(transport: Transport, addr: str) -> Tuple[Sender, Enqueuer]:
    sender, enqueuer = await Sender.connect(transport, Plain(), addr)
    return await generate_auth_key(sender, enqueuer)


async def generate_auth_key(
    sender: Sender,
    enqueuer: Enqueuer,
) -> Tuple[Sender, Enqueuer]:
    request, data = authentication.step1()
    response = await sender.send(request)
    request, data = authentication.step2(data, response)
    response = await sender.send(request)
    request, data = authentication.step3(data, response)
    response = await sender.send(request)
    finished = authentication.create_key(data, response)
    auth_key = finished.auth_key
    time_offset = finished.time_offset
    first_salt = finished.first_salt

    return (
        Sender(
            _reader=sender._reader,
            _writer=sender._writer,
            _transport=sender._transport,
            _mtp=Encrypted(auth_key, time_offset=time_offset, first_salt=first_salt),
            _mtp_buffer=sender._mtp_buffer,
            _requests=sender._requests,
            _request_rx=sender._request_rx,
            _next_ping=time.time() + PING_DELAY,
            _read_buffer=sender._read_buffer,
            _write_drain_pending=sender._write_drain_pending,
        ),
        enqueuer,
    )


async def connect_with_auth(
    transport: Transport,
    addr: str,
    auth_key: bytes,
) -> Tuple[Sender, Enqueuer]:
    return await Sender.connect(
        transport, Encrypted(AuthKey.from_bytes(auth_key)), addr
    )
