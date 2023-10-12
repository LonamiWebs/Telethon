from __future__ import annotations

import asyncio
import itertools
import logging
import platform
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List, Optional, Tuple, TypeVar

from ....version import __version__
from ...mtproto import Full, RpcError
from ...mtsender import Sender
from ...mtsender import connect as connect_without_auth
from ...mtsender import connect_with_auth
from ...session import DataCenter
from ...session import User as SessionUser
from ...tl import LAYER, Request, functions, types
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
    device_model: str = field(default_factory=default_device_model)
    system_version: str = field(default_factory=default_system_version)
    app_version: str = __version__
    system_lang_code: str = "en"
    lang_code: str = "en"
    catch_up: bool = False
    datacenter: Optional[DataCenter] = None
    flood_sleep_threshold: Optional[int] = 60
    update_queue_limit: Optional[int] = None


KNOWN_DC = [
    DataCenter(id=1, addr="149.154.175.53:443", auth=None),
    DataCenter(id=2, addr="149.154.167.51:443", auth=None),
    DataCenter(id=3, addr="149.154.175.100:443", auth=None),
    DataCenter(id=4, addr="149.154.167.92:443", auth=None),
    DataCenter(id=5, addr="91.108.56.190:443", auth=None),
]

DEFAULT_DC = 2


async def connect_sender(
    config: Config,
    dc: DataCenter,
    base_logger: logging.Logger,
) -> Tuple[Sender, List[DataCenter]]:
    transport = Full()

    if dc.auth:
        sender = await connect_with_auth(
            transport, dc.id, dc.addr, dc.auth, base_logger
        )
    else:
        sender = await connect_without_auth(transport, dc.id, dc.addr, base_logger)

    # TODO handle -404 (we had a previously-valid authkey, but server no longer knows about it)
    remote_config = await sender.invoke(
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

    latest_dcs = []
    append_current = True
    for opt in types.Config.from_bytes(remote_config).dc_options:
        assert isinstance(opt, types.DcOption)
        latest_dcs.append(
            DataCenter(
                id=opt.id,
                addr=opt.ip_address,
                auth=sender.auth_key if sender.dc_id == opt.id else None,
            )
        )
        if sender.dc_id == opt.id:
            append_current = False

    if append_current:
        # Current config has no DC with current ID.
        # Append it to preserve the authorization key.
        latest_dcs.append(
            DataCenter(id=sender.dc_id, addr=sender.addr, auth=sender.auth_key)
        )

    return sender, latest_dcs


async def connect(self: Client) -> None:
    if self._sender:
        return

    if session := await self._storage.load():
        self._session = session

    if dc := self._config.datacenter:
        # Datacenter override, reusing the session's auth-key unless already present.
        datacenter = (
            dc
            if dc.auth
            else DataCenter(
                id=dc.id,
                addr=dc.addr,
                auth=next(
                    (d.auth for d in self._session.dcs if d.id == dc.id and d.auth),
                    None,
                ),
            )
        )
    else:
        # Reuse the session's datacenter, falling back to defaults if not found.
        datacenter = datacenter_for_id(
            self, self._session.user.dc if self._session.user else DEFAULT_DC
        )

    self._sender, self._session.dcs = await connect_sender(
        self._config, datacenter, self._logger
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
            if not self._session.user:
                me = await self.get_me()
                assert me is not None
                self._session.user = SessionUser(
                    id=me.id, dc=self._sender.dc_id, bot=me.bot, username=me.username
                )
                packed = me.pack()
                assert packed is not None
                self._chat_hashes.set_self_user(packed)

    self._dispatcher = asyncio.create_task(dispatcher(self))


def datacenter_for_id(client: Client, dc_id: int) -> DataCenter:
    try:
        return next(
            dc
            for dc in itertools.chain(client._session.dcs, KNOWN_DC)
            if dc.id == dc_id
        )
    except StopIteration:
        raise ValueError(f"no datacenter found for id: {dc_id}") from None


async def disconnect(self: Client) -> None:
    if not self._sender:
        return
    assert self._dispatcher

    self._dispatcher.cancel()
    try:
        await self._dispatcher
    except Exception:
        self._logger.exception(
            "unhandled exception when cancelling dispatcher; this is a bug"
        )
    finally:
        self._dispatcher = None

    try:
        await self._sender.disconnect()
    except Exception:
        self._logger.exception("unhandled exception during disconnect; this is a bug")
    finally:
        self._sender = None

    self._session.state = self._message_box.session_state()
    await self._storage.save(self._session)


async def invoke_request(
    client: Client,
    sender: Sender,
    lock: asyncio.Lock,
    request: Request[Return],
) -> Return:
    slept_flood = False
    sleep_thresh = client._config.flood_sleep_threshold or 0
    rx = sender.enqueue(request)
    while True:
        while not rx.done():
            await step_sender(client, sender, lock)
        try:
            response = rx.result()
            break
        except RpcError as e:
            if (
                e.code == 420
                and e.value is not None
                and not slept_flood
                and e.value < sleep_thresh
            ):
                await asyncio.sleep(e.value)
                slept_flood = True
                rx = sender.enqueue(request)
                continue
            else:
                raise adapt_rpc(e) from None
    return request.deserialize_response(response)


async def step(client: Client) -> None:
    if client._sender:
        await step_sender(client, client._sender, client._sender_lock)


async def step_sender(client: Client, sender: Sender, lock: asyncio.Lock) -> None:
    if lock.locked():
        async with lock:
            pass
    else:
        async with lock:
            updates = await sender.step()
        process_socket_updates(client, updates)


async def run_until_disconnected(self: Client) -> None:
    while self.connected:
        await step(self)


def connected(client: Client) -> bool:
    return client._sender is not None
