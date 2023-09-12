from __future__ import annotations

import asyncio
import platform
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional, TypeVar

from ....version import __version__
from ...mtproto import Full, RpcError
from ...mtsender import Sender
from ...mtsender import connect as connect_without_auth
from ...mtsender import connect_with_auth
from ...session import DataCenter, Session
from ...tl import LAYER, Request, functions
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
    session: Session
    api_id: int
    api_hash: str
    device_model: str = field(default_factory=default_device_model)
    system_version: str = field(default_factory=default_system_version)
    app_version: str = __version__
    system_lang_code: str = "en"
    lang_code: str = "en"
    catch_up: bool = False
    server_addr: Optional[str] = None
    flood_sleep_threshold: Optional[int] = 60
    update_queue_limit: Optional[int] = None


# dc_id to IPv4 and port pair
DC_ADDRESSES = [
    "0.0.0.0:0",
    "149.154.175.53:443",
    "149.154.167.51:443",
    "149.154.175.100:443",
    "149.154.167.92:443",
    "91.108.56.190:443",
]

DEFAULT_DC = 2


async def connect_sender(dc_id: int, config: Config) -> Sender:
    transport = Full()

    if config.server_addr:
        addr = config.server_addr
    else:
        addr = DC_ADDRESSES[dc_id]

    auth_key: Optional[bytes] = None
    for dc in config.session.dcs:
        if dc.id == dc_id:
            if dc.auth:
                auth_key = dc.auth
            break

    if auth_key:
        sender = await connect_with_auth(transport, addr, auth_key)
    else:
        sender = await connect_without_auth(transport, addr)
        for dc in config.session.dcs:
            if dc.id == dc_id:
                dc.auth = sender.auth_key
                break
        else:
            config.session.dcs.append(
                DataCenter(id=dc_id, addr=addr, auth=sender.auth_key)
            )

    # TODO handle -404 (we had a previously-valid authkey, but server no longer knows about it)
    # TODO all up-to-date server addresses should be stored in the session for future initial connections
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
    remote_config

    return sender


async def connect(self: Client) -> None:
    if self._sender:
        return

    if session := await self._storage.load():
        self._config.session = session
    self._sender = await connect_sender(self._dc_id, self._config)

    if self._message_box.is_empty() and self._config.session.user:
        try:
            await self(functions.updates.get_state())
        except RpcError as e:
            if e.code == 401:
                self._config.session.user = None
        except Exception as e:
            pass

    self._dispatcher = asyncio.create_task(dispatcher(self))


async def disconnect(self: Client) -> None:
    if not self._sender:
        return
    assert self._dispatcher

    self._dispatcher.cancel()
    try:
        await self._dispatcher
    except asyncio.CancelledError:
        pass
    except Exception:
        pass  # TODO log
    finally:
        self._dispatcher = None

    try:
        await self._sender.disconnect()
    except Exception:
        pass  # TODO log
    finally:
        self._sender = None

    self._config.session.state = self._message_box.session_state()
    await self._storage.save(self._config.session)


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
                raise
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
