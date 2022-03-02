import asyncio
import inspect
import itertools
import typing
import dataclasses

from .. import errors, _tl
from .._misc import helpers, utils, requestiter, hints
from ..types import _custom

_MAX_CHUNK_SIZE = 100

if typing.TYPE_CHECKING:
    from .telegramclient import TelegramClient


def _dialog_message_key(peer, message_id):
    """
    Get the key to get messages from a dialog.

    We cannot just use the message ID because channels share message IDs,
    and the peer ID is required to distinguish between them. But it is not
    necessary in small group chats and private chats.
    """
    return (peer.channel_id if isinstance(peer, _tl.PeerChannel) else None), message_id


class _DialogsIter(requestiter.RequestIter):
    async def _init(
            self, offset_date, offset_id, offset_peer, ignore_pinned, ignore_migrated, folder
    ):
        self.request = _tl.fn.messages.GetDialogs(
            offset_date=offset_date,
            offset_id=offset_id,
            offset_peer=offset_peer,
            limit=1,
            hash=0,
            exclude_pinned=ignore_pinned,
            folder_id=folder
        )

        if self.limit <= 0:
            # Special case, get a single dialog and determine count
            dialogs = await self.client(self.request)
            self.total = getattr(dialogs, 'count', len(dialogs.dialogs))
            raise StopAsyncIteration

        self.seen = set()
        self.offset_date = offset_date
        self.ignore_migrated = ignore_migrated

    async def _load_next_chunk(self):
        self.request = dataclasses.replace(self.request, limit=min(self.left, _MAX_CHUNK_SIZE))
        r = await self.client(self.request)

        self.total = getattr(r, 'count', len(r.dialogs))

        entities = {utils.get_peer_id(x): x
                    for x in itertools.chain(r.users, r.chats)
                    if not isinstance(x, (_tl.UserEmpty, _tl.ChatEmpty))}

        messages = {
            _dialog_message_key(m.peer_id, m.id): _custom.Message._new(self.client, m, entities, None)
            for m in r.messages
        }

        for d in r.dialogs:
            # We check the offset date here because Telegram may ignore it
            message = messages.get(_dialog_message_key(d.peer, d.top_message))
            if self.offset_date:
                date = getattr(message, 'date', None)
                if not date or date.timestamp() > self.offset_date.timestamp():
                    continue

            peer_id = utils.get_peer_id(d.peer)
            if peer_id not in self.seen:
                self.seen.add(peer_id)
                if peer_id not in entities:
                    # > In which case can a UserEmpty appear in the list of banned members?
                    # > In a very rare cases. This is possible but isn't an expected behavior.
                    # Real world example: https://t.me/TelethonChat/271471
                    continue

                cd = _custom.Dialog(self.client, d, entities, message)
                if cd.dialog.pts:
                    self.client._channel_pts[cd.id] = cd.dialog.pts

                if not self.ignore_migrated or getattr(
                        cd.entity, 'migrated_to', None) is None:
                    self.buffer.append(cd)

        if len(r.dialogs) < self.request.limit\
                or not isinstance(r, _tl.messages.DialogsSlice):
            # Less than we requested means we reached the end, or
            # we didn't get a DialogsSlice which means we got all.
            return True

        # We can't use `messages[-1]` as the offset ID / date.
        # Why? Because pinned dialogs will mess with the order
        # in this list. Instead, we find the last dialog which
        # has a message, and use it as an offset.
        last_message = next(filter(None, (
            messages.get(_dialog_message_key(d.peer, d.top_message))
            for d in reversed(r.dialogs)
        )), None)

        self.request = dataclasses.replace(
            self.request,
            exclude_pinned=True,
            offset_id=last_message.id if last_message else 0,
            offset_date=last_message.date if last_message else None,
            offset_peer=self.buffer[-1].input_entity,
        )


class _DraftsIter(requestiter.RequestIter):
    async def _init(self, entities, **kwargs):
        if not entities:
            r = await self.client(_tl.fn.messages.GetAllDrafts())
            items = r.updates
        else:
            peers = []
            for entity in entities:
                peers.append(_tl.InputDialogPeer(
                    await self.client._get_input_peer(entity)))

            r = await self.client(_tl.fn.messages.GetPeerDialogs(peers))
            items = r.dialogs

        # TODO Maybe there should be a helper method for this?
        entities = {utils.get_peer_id(x): x
                    for x in itertools.chain(r.users, r.chats)}

        self.buffer.extend(
            _custom.Draft(self.client, entities[utils.get_peer_id(d.peer)], d.draft)
            for d in items
        )

    async def _load_next_chunk(self):
        return []


def get_dialogs(
        self: 'TelegramClient',
        limit: float = (),
        *,
        offset_date: 'hints.DateLike' = None,
        offset_id: int = 0,
        offset_peer: 'hints.DialogLike' = _tl.InputPeerEmpty(),
        ignore_pinned: bool = False,
        ignore_migrated: bool = False,
        folder: int = None,
) -> _DialogsIter:
    return _DialogsIter(
        self,
        limit,
        offset_date=offset_date,
        offset_id=offset_id,
        offset_peer=offset_peer,
        ignore_pinned=ignore_pinned,
        ignore_migrated=ignore_migrated,
        folder=folder
    )


def get_drafts(
        self: 'TelegramClient',
        dialog: 'hints.DialogsLike' = None
) -> _DraftsIter:
    limit = None
    if dialog:
        if not utils.is_list_like(dialog):
            dialog = (dialog,)
        limit = len(dialog)

    return _DraftsIter(self, limit, entities=dialog)


async def delete_dialog(
        self: 'TelegramClient',
        dialog: 'hints.DialogLike',
        *,
        revoke: bool = False
):
    # If we have enough information (`Dialog.delete` gives it to us),
    # then we know we don't have to kick ourselves in deactivated chats.
    if isinstance(entity, _tl.Chat):
        deactivated = entity.deactivated
    else:
        deactivated = False

    entity = await self._get_input_peer(dialog)
    ty = helpers._entity_type(entity)
    if ty == helpers._EntityType.CHANNEL:
        return await self(_tl.fn.channels.LeaveChannel(entity))

    if ty == helpers._EntityType.CHAT and not deactivated:
        try:
            result = await self(_tl.fn.messages.DeleteChatUser(
                entity.chat_id, _tl.InputUserSelf(), revoke_history=revoke
            ))
        except errors.PEER_ID_INVALID:
            # Happens if we didn't have the deactivated information
            result = None
    else:
        result = None

    if not await self.is_bot():
        await self(_tl.fn.messages.DeleteHistory(entity, 0, revoke=revoke))

    return result
