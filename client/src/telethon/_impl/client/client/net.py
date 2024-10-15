from __future__ import annotations

import asyncio
import itertools
import logging
import platform
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional, TypeVar

from ....version import __version__
from ...mtproto import BadStatusError, Full, RpcError
from ...mtsender import Connector, Sender
from ...mtsender import connect as do_connect_sender
from ...session import DataCenter
from ...session import User as SessionUser
from ...tl import LAYER, Request, abcs, functions, types
from ..errors import adapt_rpc
from .updates import dispatcher, process_socket_updates

if TYPE_CHECKING:
    from .client import Client


Return = TypeVar("Return")


def default_device_model() -> str:
    system = platform.uname()
    if system.machine in ("x86_64", "AMD64"):
        return "PC 64bit"
    elif system.machine in ("i386", "i686", "x86"):
        return "PC 32bit"
    else:
        return system.machine or "Unknown"


def default_system_version() -> str:
    system = platform.uname()
    return re.sub(r"-.+", "", system.release) or "1.0"


@dataclass
class Config:
    api_id: int
    api_hash: str
    base_logger: logging.Logger
    connector: Connector
    device_model: str = field(default_factory=default_device_model)
    system_version: str = field(default_factory=default_system_version)
    app_version: str = __version__
    system_lang_code: str = "en"
    lang_code: str = "en"
    catch_up: bool = False
    datacenter: Optional[DataCenter] = None
    flood_sleep_threshold: int = 60
    update_queue_limit: Optional[int] = None


KNOWN_DCS = [
    DataCenter(id=1, ipv4_addr="149.154.175.53:443", ipv6_addr=None, auth=None),
    DataCenter(id=2, ipv4_addr="149.154.167.51:443", ipv6_addr=None, auth=None),
    DataCenter(id=3, ipv4_addr="149.154.175.100:443", ipv6_addr=None, auth=None),
    DataCenter(id=4, ipv4_addr="149.154.167.92:443", ipv6_addr=None, auth=None),
    DataCenter(id=5, ipv4_addr="91.108.56.190:443", ipv6_addr=None, auth=None),
]

DEFAULT_DC = 2


def as_concrete_dc_option(opt: abcs.DcOption) -> types.DcOption:
    assert isinstance(opt, types.DcOption)
    return opt


async def connect_sender(
    config: Config,
    known_dcs: list[DataCenter],
    dc: DataCenter,
    force_auth_gen: bool = False,
) -> tuple[Sender, list[DataCenter]]:
    # Only the ID of the input DC may be known.
    # Find the corresponding address and authentication key if needed.
    addr = dc.ipv4_addr or next(
        d.ipv4_addr
        for d in itertools.chain(known_dcs, KNOWN_DCS)
        if d.id == dc.id and d.ipv4_addr
    )
    auth = (
        None
        if force_auth_gen
        else dc.auth
        or (next((d.auth for d in known_dcs if d.id == dc.id and d.auth), None))
    )

    sender = await do_connect_sender(
        Full(),
        dc.id,
        addr,
        auth_key=auth,
        base_logger=config.base_logger,
        connector=config.connector,
    )

    try:
        remote_config_data = await sender.invoke(
            functions.invoke_with_layer(
                layer=LAYER,
                query=functions.init_connection(
                    api_id=config.api_id,
                    device_model=config.device_model,
                    system_version=config.system_version,
                    app_version=config.app_version,
                    system_lang_code=config.system_lang_code,
                    lang_pack="",
                    lang_code=config.lang_code,
                    proxy=None,
                    params=None,
                    query=functions.help.get_config(),
                ),
            )
        )
    except BadStatusError as e:
        if e.status == 404 and auth:
            dc = DataCenter(
                id=dc.id, ipv4_addr=dc.ipv4_addr, ipv6_addr=dc.ipv6_addr, auth=None
            )
            config.base_logger.warning(
                "datacenter could not find stored auth; will retry generating a new one: %s",
                dc,
            )
            return await connect_sender(config, known_dcs, dc, force_auth_gen=True)
        else:
            raise

    remote_config = types.Config.from_bytes(remote_config_data)

    # Filter the primary data-centers to persist, static first.
    dc_options = [
        opt
        for opt in map(as_concrete_dc_option, remote_config.dc_options)
        if not (opt.media_only or opt.tcpo_only or opt.cdn)
    ]
    dc_options.sort(key=lambda opt: opt.static, reverse=True)

    latest_dcs: dict[int, DataCenter] = {}
    for opt in dc_options:
        dc = latest_dcs.setdefault(opt.id, DataCenter(id=opt.id))
        if opt.ipv6:
            if not dc.ipv6_addr:
                dc.ipv6_addr = f"{opt.ip_address}:{opt.port}"
        else:
            if not dc.ipv4_addr:
                dc.ipv4_addr = f"{opt.ip_address}:{opt.port}"

    # Restore only missing information.
    for dc in itertools.chain(
        [DataCenter(id=sender.dc_id, ipv4_addr=sender.addr, auth=sender.auth_key)],
        known_dcs,
    ):
        saved_dc = latest_dcs.setdefault(sender.dc_id, DataCenter(id=dc.id))
        saved_dc.ipv4_addr = saved_dc.ipv4_addr or dc.ipv4_addr
        saved_dc.ipv6_addr = saved_dc.ipv6_addr or dc.ipv6_addr
        saved_dc.auth = saved_dc.auth or dc.auth

    session_dcs = [dc for _, dc in sorted(latest_dcs.items(), key=lambda t: t[0])]
    return sender, session_dcs


async def connect(self: Client) -> None:
    if self._sender:
        return

    if session := await self._storage.load():
        self._session = session

    datacenter = self._config.datacenter or DataCenter(
        id=self._session.user.dc if self._session.user else DEFAULT_DC
    )
    self._sender, self._session.dcs = await connect_sender(
        self._config, self._session.dcs, datacenter
    )

    if self._message_box.is_empty() and self._session.user:
        try:
            await self(functions.updates.get_state())
        except RpcError as e:
            if e.code == 401:
                self._session.user = None
        except Exception:
            pass
        else:
            me = await self.get_me()
            assert me is not None
            self._chat_hashes.set_self_user(me.id, me.bot)
            self._session.user = SessionUser(
                id=me.id, dc=self._sender.dc_id, bot=me.bot, username=me.username
            )

    self._dispatcher = asyncio.create_task(dispatcher(self))


async def disconnect(self: Client) -> None:
    if not self._sender:
        return
    assert self._dispatcher

    sender = self._sender
    self._sender = None  # treated as disconnected

    self._dispatcher.cancel()
    try:
        await self._dispatcher
    except asyncio.CancelledError:
        pass
    except Exception:
        self._config.base_logger.exception(
            "unhandled exception when cancelling dispatcher; this is a bug"
        )
    finally:
        self._dispatcher = None

    try:
        await sender.disconnect()
    except Exception:
        self._config.base_logger.exception(
            "unhandled exception during disconnect; this is a bug"
        )

    try:
        if self._session.user:
            # Only save if we haven't logged out (prevents double-save)
            self._session.state = self._message_box.session_state()
            await self._storage.save(self._session)
    finally:
        await self._storage.close()


async def invoke_request(
    client: Client,
    request: Request[Return],
) -> Return:
    if not client._sender:
        raise ConnectionError("not connected")

    sleep_thresh = client._config.flood_sleep_threshold
    rx = client._sender.enqueue(request)
    while True:
        while not rx.done():
            await step_sender(client)
        try:
            response = rx.result()
            break
        except RpcError as e:
            if e.code == 420 and e.value is not None and e.value < sleep_thresh:
                await asyncio.sleep(e.value)
                sleep_thresh -= e.value
                rx = client._sender.enqueue(request)
                continue
            else:
                raise adapt_rpc(e) from None
    return request.deserialize_response(response)


async def step_sender(client: Client) -> None:
    try:
        assert client._sender
        updates = await client._sender.get_updates()
    except ConnectionError:
        if client.connected:
            raise
        else:
            # disconnect was called, so the socket returning 0 bytes is expected
            return

    process_socket_updates(client, updates)


async def step(self: Client) -> None:
    if self._sender:
        await step_sender(self)


async def run_until_disconnected(self: Client) -> None:
    while self.connected:
        await step(self)


def connected(client: Client) -> bool:
    return client._sender is not None
