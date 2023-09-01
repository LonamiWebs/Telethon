from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional, Union

from ...tl import abcs, types
from ..types.message import Message

if TYPE_CHECKING:
    from .client import Client


def iter_messages(self: Client) -> None:
    self
    raise NotImplementedError


async def send_message(self: Client) -> None:
    self
    raise NotImplementedError


async def forward_messages(self: Client) -> None:
    self
    raise NotImplementedError


async def edit_message(self: Client) -> None:
    self
    raise NotImplementedError


async def delete_messages(self: Client) -> None:
    self
    raise NotImplementedError


async def send_read_acknowledge(self: Client) -> None:
    self
    raise NotImplementedError


async def pin_message(self: Client) -> None:
    self
    raise NotImplementedError


async def unpin_message(self: Client) -> None:
    self
    raise NotImplementedError


def find_updates_message(
    self: Client,
    result: abcs.Updates,
    random_id: int,
    chat: Optional[abcs.InputPeer],
) -> Message:
    if isinstance(result, types.UpdateShort):
        updates = [result.update]
        entities: Dict[int, object] = {}
    elif isinstance(result, (types.Updates, types.UpdatesCombined)):
        updates = result.updates
        entities = {}
        raise NotImplementedError()
    else:
        return Message._from_raw(
            types.MessageEmpty(id=0, peer_id=self._input_as_peer(chat))
        )

    random_to_id = {}
    id_to_message = {}
    for update in updates:
        if isinstance(update, types.UpdateMessageId):
            random_to_id[update.random_id] = update.id

        elif isinstance(
            update,
            (
                types.UpdateNewChannelMessage,
                types.UpdateNewMessage,
                types.UpdateEditMessage,
                types.UpdateEditChannelMessage,
                types.UpdateNewScheduledMessage,
            ),
        ):
            assert isinstance(
                update.message,
                (types.Message, types.MessageService, types.MessageEmpty),
            )
            id_to_message[update.message.id] = update.message

        elif isinstance(update, types.UpdateMessagePoll):
            raise NotImplementedError()

    return Message._from_raw(id_to_message[random_to_id[random_id]])
