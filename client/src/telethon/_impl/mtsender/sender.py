import asyncio
import logging
import struct
import time
from abc import ABC
from asyncio import Event, Future, Lock
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Generic, Optional, Protocol, Type, TypeVar

from typing_extensions import Self

from ..crypto import AuthKey
from ..mtproto import (
    BadMessageError,
    Encrypted,
    MissingBytesError,
    MsgId,
    Mtp,
    Plain,
    RpcError,
    RpcResult,
    Transport,
    Update,
    authentication,
)
from ..tl import Request as RemoteCall
from ..tl.abcs import Updates
from ..tl.core import Serializable
from ..tl.mtproto.functions import ping_delay_disconnect
from ..tl.types import UpdateDeleteMessages, UpdateShort
from ..tl.types.messages import AffectedFoundMessages, AffectedHistory, AffectedMessages

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


class AsyncReader(Protocol):
    """
    A :class:`asyncio.StreamReader`-like class.
    """

    async def read(self, n: int) -> bytes:
        """
        Must behave like :meth:`asyncio.StreamReader.read`.

        :param n:
            Amount of bytes to read at most.
        """
        raise NotImplementedError


class AsyncWriter(Protocol):
    """
    A :class:`asyncio.StreamWriter`-like class.
    """

    def write(self, data: bytes | bytearray | memoryview) -> None:
        """
        Must behave like :meth:`asyncio.StreamWriter.write`.

        :param data:
            Data that must be entirely written or buffered until :meth:`drain` is called.
        """

    async def drain(self) -> None:
        """
        Must behave like :meth:`asyncio.StreamWriter.drain`.
        """

    def close(self) -> None:
        """
        Must behave like :meth:`asyncio.StreamWriter.close`.
        """

    async def wait_closed(self) -> None:
        """
        Must behave like :meth:`asyncio.StreamWriter.wait_closed`.
        """


class Connector(Protocol):
    """
    A *Connector* is any function that takes in the following two positional parameters as input:

    * The ``ip`` address as a :class:`str`. This might be either a IPv4 or IPv6.
    * The ``port`` as a :class:`int`. This will be a number below 2¹⁶, often 443.

    and returns a :class:`tuple`\\ [:class:`AsyncReader`, :class:`AsyncWriter`].

    You can use a custom connector to connect to Telegram through proxies.
    The library will only ever open remote connections through this function.

    The default connector is :func:`asyncio.open_connection`, defined as:

    .. code-block:: python

        default_connector = lambda ip, port: asyncio.open_connection(ip, port)

    If your connector needs additional parameters, you can use either the :keyword:`lambda` syntax or :func:`functools.partial`.

    .. seealso::

        The :doc:`/concepts/datacenters` concept has examples on how to combine proxy libraries with Telethon.
    """

    async def __call__(self, ip: str, port: int) -> tuple[AsyncReader, AsyncWriter]:
        raise NotImplementedError


class RequestState(ABC):
    pass


class NotSerialized(RequestState):
    pass


class Serialized(RequestState):
    __slots__ = ("msg_id", "container_msg_id")

    def __init__(self, msg_id: MsgId) -> None:
        self.msg_id = msg_id
        self.container_msg_id = msg_id


class Sent(RequestState):
    __slots__ = ("msg_id", "container_msg_id")

    def __init__(self, msg_id: MsgId, container_msg_id: MsgId) -> None:
        self.msg_id = msg_id
        self.container_msg_id = container_msg_id


Return = TypeVar("Return")


@dataclass
class Request(Generic[Return]):
    body: bytes
    state: RequestState
    result: Future[Return]


@dataclass
class Sender:
    dc_id: int
    addr: str
    lock: Lock
    _logger: logging.Logger
    _reader: AsyncReader
    _writer: AsyncWriter
    _reading: bool
    _writing: bool
    _transport: Transport
    _mtp: Mtp
    _mtp_buffer: bytearray
    _updates: list[Updates]
    _requests: list[Request[object]]
    _response_event: Event
    _read_buffer: bytearray

    @classmethod
    async def connect(
        cls,
        transport: Transport,
        mtp: Mtp,
        dc_id: int,
        addr: str,
        *,
        connector: Connector,
        base_logger: logging.Logger,
    ) -> Self:
        ip, port = addr.split(":")
        reader, writer = await connector(ip, int(port))

        return cls(
            dc_id=dc_id,
            addr=addr,
            lock=Lock(),
            _logger=base_logger.getChild("mtsender"),
            _reading=False,
            _writing=False,
            _reader=reader,
            _writer=writer,
            _transport=transport,
            _mtp=mtp,
            _mtp_buffer=bytearray(),
            _updates=[],
            _requests=[],
            _response_event=Event(),
            _read_buffer=bytearray(),
        )

    async def disconnect(self) -> None:
        self._writer.close()
        await self._writer.wait_closed()

    def enqueue(self, request: RemoteCall[Return]) -> Future[bytes]:
        rx = self._enqueue_body(bytes(request))
        return rx

    async def invoke(self, request: RemoteCall[Return]) -> bytes:
        rx = self._enqueue_body(bytes(request))
        return await self._step_until_receive(rx)

    async def send(self, body: bytes) -> bytes:
        rx = self._enqueue_body(body)
        return await self._step_until_receive(rx)

    def _enqueue_body(self, body: bytes) -> Future[bytes]:
        oneshot = asyncio.get_running_loop().create_future()
        self._requests.append(Request(body=body, state=NotSerialized(), result=oneshot))
        return oneshot

    async def _step_until_receive(self, rx: Future[bytes]) -> bytes:
        while True:
            await self.step()
            if rx.done():
                return rx.result()

    async def step(self) -> None:
        if not self._writing:
            self._writing = True
            await self._try_fill_write()
            self._writing = False

        if not self._reading:
            self._reading = True
            self._response_event.clear()
            await self._try_read()
            self._reading = False
        else:
            await self._response_event.wait()

    def pop_updates(self) -> list[Updates]:
        updates = self._updates[:]
        self._updates.clear()
        return updates

    async def _try_read(self) -> None:
        try:
            async with asyncio.timeout(PING_DELAY):
                recv_data = await self._reader.read(MAXIMUM_DATA)
        except TimeoutError:
            self._on_ping_timeout()
        else:
            self._on_net_read(recv_data)

    async def _try_fill_write(self) -> None:
        for request in self._requests:
            if isinstance(request.state, NotSerialized):
                if (msg_id := self._mtp.push(request.body)) is not None:
                    request.state = Serialized(msg_id)
                else:
                    break

        result = self._mtp.finalize()
        if result:
            container_msg_id, mtp_buffer = result

            self._transport.pack(mtp_buffer, self._writer.write)
            for request in self._requests:
                if isinstance(request.state, Serialized):
                    request.state = Sent(request.state.msg_id, container_msg_id)

            await self._writer.drain()

    def _on_net_read(self, read_buffer: bytes) -> None:
        if not read_buffer:
            raise ConnectionResetError("read 0 bytes")

        self._read_buffer += read_buffer

        while self._read_buffer:
            self._mtp_buffer.clear()
            try:
                n = self._transport.unpack(self._read_buffer, self._mtp_buffer)
            except MissingBytesError:
                break
            else:
                del self._read_buffer[:n]
                self._process_mtp_buffer()
                self._response_event.set()

    def _on_ping_timeout(self) -> None:
        ping_id = generate_random_id()
        self._enqueue_body(
            bytes(
                ping_delay_disconnect(
                    ping_id=ping_id, disconnect_delay=NO_PING_DISCONNECT
                )
            )
        )

    def _process_mtp_buffer(self) -> None:
        results = self._mtp.deserialize(self._mtp_buffer)

        for result in results:
            if isinstance(result, Update):
                self._process_update(result.body)
            elif isinstance(result, RpcResult):
                self._process_result(result)
            elif isinstance(result, RpcError):
                self._process_error(result)
            else:
                self._process_bad_message(result)

    def _process_update(self, update: bytes | bytearray | memoryview) -> None:
        try:
            self._updates.append(Updates.from_bytes(update))
        except ValueError:
            cid = struct.unpack_from("I", update)[0]
            alt_classes: tuple[Type[Serializable], ...] = (
                AffectedFoundMessages,
                AffectedHistory,
                AffectedMessages,
            )
            for cls in alt_classes:
                if cid == cls.constructor_id():
                    affected = cls.from_bytes(update)
                    # mypy struggles with the types here quite a bit
                    assert isinstance(
                        affected,
                        (
                            AffectedFoundMessages,
                            AffectedHistory,
                            AffectedMessages,
                        ),
                    )
                    self._updates.append(
                        UpdateShort(
                            update=UpdateDeleteMessages(
                                messages=[],
                                pts=affected.pts,
                                pts_count=affected.pts_count,
                            ),
                            date=0,
                        )
                    )
                    break
            else:
                self._logger.warning(
                    "failed to deserialize incoming update; make sure the session is not in use elsewhere: %s",
                    update.hex(),
                )
                return

    def _process_result(self, result: RpcResult) -> None:
        req = self._pop_request(result.msg_id)

        if req:
            assert len(result.body) >= 4
            req.result.set_result(result.body)
        else:
            self._logger.warning(
                "telegram sent rpc_result for unknown msg_id=%d: %s",
                result.msg_id,
                result.body.hex(),
            )

    def _process_error(self, result: RpcError) -> None:
        req = self._pop_request(result.msg_id)

        if req:
            result._caused_by = struct.unpack_from("<I", req.body)[0]
            req.result.set_exception(result)
        else:
            self._logger.warning(
                "telegram sent rpc_error for unknown msg_id=%d: %s",
                result.msg_id,
                result,
            )

    def _process_bad_message(self, result: BadMessageError) -> None:
        for req in self._drain_requests(result.msg_id):
            if result.retryable:
                self._logger.log(
                    result.severity,
                    "telegram notified of bad msg_id=%d; will attempt to resend request: %s",
                    result.msg_id,
                    result,
                )
                req.state = NotSerialized()
                self._requests.append(req)
            else:
                self._logger.log(
                    result.severity,
                    "telegram notified of bad msg_id=%d; impossible to retry: %s",
                    result.msg_id,
                    result,
                )
                result._caused_by = struct.unpack_from("<I", req.body)[0]
                req.result.set_exception(result)

    def _pop_request(self, msg_id: MsgId) -> Optional[Request[object]]:
        for i, req in enumerate(self._requests):
            if isinstance(req.state, Serialized) and req.state.msg_id == msg_id:
                raise RuntimeError("got response for unsent request")
            elif isinstance(req.state, Sent) and req.state.msg_id == msg_id:
                del self._requests[i]
                return req

        return None

    def _drain_requests(self, msg_id: MsgId) -> Iterator[Request[object]]:
        for i in reversed(range(len(self._requests))):
            req = self._requests[i]
            if isinstance(req.state, Serialized) and (
                req.state.msg_id == msg_id or req.state.container_msg_id == msg_id
            ):
                raise RuntimeError("got response for unsent request")
            elif isinstance(req.state, Sent) and (
                req.state.msg_id == msg_id or req.state.container_msg_id == msg_id
            ):
                yield self._requests.pop(i)

    @property
    def auth_key(self) -> Optional[bytes]:
        if isinstance(self._mtp, Encrypted):
            return self._mtp.auth_key
        else:
            return None


async def connect(
    transport: Transport,
    dc_id: int,
    addr: str,
    *,
    auth_key: Optional[bytes],
    base_logger: logging.Logger,
    connector: Connector,
) -> Sender:
    if auth_key is None:
        sender = await Sender.connect(
            transport,
            Plain(),
            dc_id,
            addr,
            connector=connector,
            base_logger=base_logger,
        )
        return await generate_auth_key(sender)
    else:
        return await Sender.connect(
            transport,
            Encrypted(AuthKey.from_bytes(auth_key)),
            dc_id,
            addr,
            connector=connector,
            base_logger=base_logger,
        )


async def generate_auth_key(sender: Sender) -> Sender:
    request, data1 = authentication.step1()
    response = await sender.send(request)
    request, data2 = authentication.step2(data1, response)
    response = await sender.send(request)
    request, data3 = authentication.step3(data2, response)
    response = await sender.send(request)
    finished = authentication.create_key(data3, response)
    auth_key = finished.auth_key
    time_offset = finished.time_offset
    first_salt = finished.first_salt

    sender._mtp = Encrypted(auth_key, time_offset=time_offset, first_salt=first_salt)
    return sender
