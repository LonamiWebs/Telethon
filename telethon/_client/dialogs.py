import asyncio
import inspect
import itertools
import typing

from .. import helpers, utils, hints, errors
from ..requestiter import RequestIter
from ..tl import types, functions, custom

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
    return (peer.channel_id if isinstance(peer, types.PeerChannel) else None), message_id


class _DialogsIter(RequestIter):
    async def _init(
            self, offset_date, offset_id, offset_peer, ignore_pinned, ignore_migrated, folder
    ):
        self.request = functions.messages.GetDialogsRequest(
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
        self.request.limit = min(self.left, _MAX_CHUNK_SIZE)
        r = await self.client(self.request)

        self.total = getattr(r, 'count', len(r.dialogs))

        entities = {utils.get_peer_id(x): x
                    for x in itertools.chain(r.users, r.chats)
                    if not isinstance(x, (types.UserEmpty, types.ChatEmpty))}

        messages = {}
        for m in r.messages:
            m._finish_init(self.client, entities, None)
            messages[_dialog_message_key(m.peer_id, m.id)] = m

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

                cd = custom.Dialog(self.client, d, entities, message)
                if cd.dialog.pts:
                    self.client._channel_pts[cd.id] = cd.dialog.pts

                if not self.ignore_migrated or getattr(
                        cd.entity, 'migrated_to', None) is None:
                    self.buffer.append(cd)

        if len(r.dialogs) < self.request.limit\
                or not isinstance(r, types.messages.DialogsSlice):
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

        self.request.exclude_pinned = True
        self.request.offset_id = last_message.id if last_message else 0
        self.request.offset_date = last_message.date if last_message else None
        self.request.offset_peer = self.buffer[-1].input_entity


class _DraftsIter(RequestIter):
    async def _init(self, entities, **kwargs):
        if not entities:
            r = await self.client(functions.messages.GetAllDraftsRequest())
            items = r.updates
        else:
            peers = []
            for entity in entities:
                peers.append(types.InputDialogPeer(
                    await self.client.get_input_entity(entity)))

            r = await self.client(functions.messages.GetPeerDialogsRequest(peers))
            items = r.dialogs

        # TODO Maybe there should be a helper method for this?
        entities = {utils.get_peer_id(x): x
                    for x in itertools.chain(r.users, r.chats)}

        self.buffer.extend(
            custom.Draft(self.client, entities[utils.get_peer_id(d.peer)], d.draft)
            for d in items
        )

    async def _load_next_chunk(self):
        return []


def iter_dialogs(
        self: 'TelegramClient',
        limit: float = None,
        *,
        offset_date: 'hints.DateLike' = None,
        offset_id: int = 0,
        offset_peer: 'hints.EntityLike' = types.InputPeerEmpty(),
        ignore_pinned: bool = False,
        ignore_migrated: bool = False,
        folder: int = None,
        archived: bool = None
) -> _DialogsIter:
    if archived is not None:
        folder = 1 if archived else 0

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

async def get_dialogs(self: 'TelegramClient', *args, **kwargs) -> 'hints.TotalList':
    return await self.iter_dialogs(*args, **kwargs).collect()


def iter_drafts(
        self: 'TelegramClient',
        entity: 'hints.EntitiesLike' = None
) -> _DraftsIter:
    if entity and not utils.is_list_like(entity):
        entity = (entity,)

    # TODO Passing a limit here makes no sense
    return _DraftsIter(self, None, entities=entity)

async def get_drafts(
        self: 'TelegramClient',
        entity: 'hints.EntitiesLike' = None
) -> 'hints.TotalList':
    items = await self.iter_drafts(entity).collect()
    if not entity or utils.is_list_like(entity):
        return items
    else:
        return items[0]

async def edit_folder(
        self: 'TelegramClient',
        entity: 'hints.EntitiesLike' = None,
        folder: typing.Union[int, typing.Sequence[int]] = None,
        *,
        unpack=None
) -> types.Updates:
    if (entity is None) == (unpack is None):
        raise ValueError('You can only set either entities or unpack, not both')

    if unpack is not None:
        return await self(functions.folders.DeleteFolderRequest(
            folder_id=unpack
        ))

    if not utils.is_list_like(entity):
        entities = [await self.get_input_entity(entity)]
    else:
        entities = await asyncio.gather(
            *(self.get_input_entity(x) for x in entity))

    if folder is None:
        raise ValueError('You must specify a folder')
    elif not utils.is_list_like(folder):
        folder = [folder] * len(entities)
    elif len(entities) != len(folder):
        raise ValueError('Number of folders does not match number of entities')

    return await self(functions.folders.EditPeerFoldersRequest([
        types.InputFolderPeer(x, folder_id=y)
        for x, y in zip(entities, folder)
    ]))

async def delete_dialog(
        self: 'TelegramClient',
        entity: 'hints.EntityLike',
        *,
        revoke: bool = False
):
    # If we have enough information (`Dialog.delete` gives it to us),
    # then we know we don't have to kick ourselves in deactivated chats.
    if isinstance(entity, types.Chat):
        deactivated = entity.deactivated
    else:
        deactivated = False

    entity = await self.get_input_entity(entity)
    ty = helpers._entity_type(entity)
    if ty == helpers._EntityType.CHANNEL:
        return await self(functions.channels.LeaveChannelRequest(entity))

    if ty == helpers._EntityType.CHAT and not deactivated:
        try:
            result = await self(functions.messages.DeleteChatUserRequest(
                entity.chat_id, types.InputUserSelf(), revoke_history=revoke
            ))
        except errors.PeerIdInvalidError:
            # Happens if we didn't have the deactivated information
            result = None
    else:
        result = None

    if not await self.is_bot():
        await self(functions.messages.DeleteHistoryRequest(entity, 0, revoke=revoke))

    return result

def conversation(
        self: 'TelegramClient',
        entity: 'hints.EntityLike',
        *,
        timeout: float = 60,
        total_timeout: float = None,
        max_messages: int = 100,
        exclusive: bool = True,
        replies_are_responses: bool = True) -> custom.Conversation:
    return custom.Conversation(
        self,
        entity,
        timeout=timeout,
        total_timeout=total_timeout,
        max_messages=max_messages,
        exclusive=exclusive,
        replies_are_responses=replies_are_responses

    )
