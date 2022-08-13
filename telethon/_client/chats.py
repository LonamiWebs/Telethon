import asyncio
import inspect
import itertools
import string
import typing
import dataclasses

from .. import errors, _tl
from .._misc import helpers, utils, requestiter, tlobject, enums, hints
from ..types import _custom

if typing.TYPE_CHECKING:
    from .telegramclient import TelegramClient

_MAX_PARTICIPANTS_CHUNK_SIZE = 200
_MAX_ADMIN_LOG_CHUNK_SIZE = 100
_MAX_PROFILE_PHOTO_CHUNK_SIZE = 100


class _ChatAction:
    def __init__(self, client, chat, action, *, delay, auto_cancel):
        self._client = client
        self._delay = delay
        self._auto_cancel = auto_cancel
        self._request = _tl.fn.messages.SetTyping(chat, action)
        self._task = None
        self._running = False

    def __await__(self):
        return self._once().__await__()

    async def __aenter__(self):
        self._request = dataclasses.replace(self._request, peer=await self._client._get_input_peer(self._request.peer))
        self._running = True
        self._task = asyncio.create_task(self._update())
        return self

    async def __aexit__(self, *args):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

            self._task = None

    async def _once(self):
        self._request = dataclasses.replace(self._request, peer=await self._client._get_input_peer(self._request.peer))
        await self._client(_tl.fn.messages.SetTyping(self._chat, self._action))

    async def _update(self):
        try:
            while self._running:
                await self._client(self._request)
                await asyncio.sleep(self._delay)
        except ConnectionError:
            pass
        except asyncio.CancelledError:
            if self._auto_cancel:
                await self._client(_tl.fn.messages.SetTyping(
                    self._chat, _tl.SendMessageCancelAction()))

    @staticmethod
    def _parse(action):
        if isinstance(action, tlobject.TLObject) and action.SUBCLASS_OF_ID != 0x20b2cc21:
            return action

        return {
            enums.Action.TYPING: _tl.SendMessageTypingAction(),
            enums.Action.CONTACT: _tl.SendMessageChooseContactAction(),
            enums.Action.GAME: _tl.SendMessageGamePlayAction(),
            enums.Action.LOCATION: _tl.SendMessageGeoLocationAction(),
            enums.Action.STICKER: _tl.SendMessageChooseStickerAction(),
            enums.Action.RECORD_AUDIO: _tl.SendMessageRecordAudioAction(),
            enums.Action.RECORD_ROUND: _tl.SendMessageRecordRoundAction(),
            enums.Action.RECORD_VIDEO: _tl.SendMessageRecordVideoAction(),
            enums.Action.AUDIO: _tl.SendMessageUploadAudioAction(1),
            enums.Action.ROUND: _tl.SendMessageUploadRoundAction(1),
            enums.Action.VIDEO: _tl.SendMessageUploadVideoAction(1),
            enums.Action.PHOTO: _tl.SendMessageUploadPhotoAction(1),
            enums.Action.DOCUMENT: _tl.SendMessageUploadDocumentAction(1),
            enums.Action.CANCEL: _tl.SendMessageCancelAction(),
        }[enums.Action(action)]

    def progress(self, current, total):
        if hasattr(self._request.action, 'progress'):
            self._request = dataclasses.replace(
                self._request,
                action=dataclasses.replace(self._request.action, progress=100 * round(current / total))
            )


class _ParticipantsIter(requestiter.RequestIter):
    async def _init(self, entity, filter, search):
        if not filter:
            if search:
                filter = _tl.ChannelParticipantsSearch(search)
            else:
                filter = _tl.ChannelParticipantsRecent()
        else:
            filter = enums.Participant(filter)
            if filter == enums.Participant.ADMIN:
                filter = _tl.ChannelParticipantsAdmins()
            elif filter == enums.Participant.BOT:
                filter = _tl.ChannelParticipantsBots()
            elif filter == enums.Participant.KICKED:
                filter = _tl.ChannelParticipantsKicked(search)
            elif filter == enums.Participant.BANNED:
                filter = _tl.ChannelParticipantsBanned(search)
            elif filter == enums.Participant.CONTACT:
                filter = _tl.ChannelParticipantsContacts(search)
            else:
                raise RuntimeError('unhandled enum variant')

        entity = await self.client._get_input_peer(entity)
        ty = helpers._entity_type(entity)
        if search and (filter or ty != helpers._EntityType.CHANNEL):
            # We need to 'search' ourselves unless we have a PeerChannel
            search = search.casefold()

            self.filter_entity = lambda ent: (
                search in utils.get_display_name(ent).casefold() or
                search in (getattr(ent, 'username', None) or '').casefold()
            )
        else:
            self.filter_entity = lambda ent: True

        if ty == helpers._EntityType.CHANNEL:
            if self.limit <= 0:
                # May not have access to the channel, but getFull can get the .total.
                self.total = (await self.client(
                    _tl.fn.channels.GetFullChannel(entity)
                )).full_chat.participants_count
                raise StopAsyncIteration

            self.seen = set()
            self.request = _tl.fn.channels.GetParticipants(
                channel=entity,
                filter=filter or _tl.ChannelParticipantsSearch(search),
                offset=0,
                limit=_MAX_PARTICIPANTS_CHUNK_SIZE,
                hash=0
            )

        elif ty == helpers._EntityType.CHAT:
            full = await self.client(
                _tl.fn.messages.GetFullChat(entity.chat_id))
            if not isinstance(
                    full.full_chat.participants, _tl.ChatParticipants):
                # ChatParticipantsForbidden won't have ``.participants``
                self.total = 0
                raise StopAsyncIteration

            self.total = len(full.full_chat.participants.participants)

            users = {user.id: user for user in full.users}
            for participant in full.full_chat.participants.participants:
                if isinstance(participant, _tl.ChannelParticipantBanned):
                    user_id = participant.peer.user_id
                else:
                    user_id = participant.user_id
                user = users[user_id]
                if not self.filter_entity(user):
                    continue

                user = users[user_id]
                self.buffer.append(user)

            return True
        else:
            self.total = 1
            if self.limit != 0:
                user = await self.client.get_profile(entity)
                if self.filter_entity(user):
                    self.buffer.append(user)

            return True

    async def _load_next_chunk(self):
        # Only care about the limit for the first request
        # (small amount of people).
        #
        # Most people won't care about getting exactly 12,345
        # members so it doesn't really matter not to be 100%
        # precise with being out of the offset/limit here.
        self.request = dataclasses.replace(self.request, limit=min(
            self.limit - self.request.offset, _MAX_PARTICIPANTS_CHUNK_SIZE))

        if self.request.offset > self.limit:
            return True

        participants = await self.client(self.request)
        self.total = participants.count

        self.request = dataclasses.replace(self.request, offset=self.request.offset + len(participants.participants))
        users = {user.id: user for user in participants.users}
        for participant in participants.participants:
            if isinstance(participant, _tl.ChannelParticipantBanned):
                if not isinstance(participant.peer, _tl.PeerUser):
                    # May have the entire channel banned. See #3105.
                    continue
                user_id = participant.peer.user_id
            else:
                user_id = participant.user_id

            if isinstance(participant, types.ChannelParticipantLeft):
                # These participants should be ignored. See #3231.
                continue

            user = users[user_id]
            if not self.filter_entity(user) or user.id in self.seen:
                continue
            self.seen.add(user_id)
            user = users[user_id]
            self.buffer.append(user)


class _AdminLogIter(requestiter.RequestIter):
    async def _init(
            self, entity, admins, search, min_id, max_id,
            join, leave, invite, restrict, unrestrict, ban, unban,
            promote, demote, info, settings, pinned, edit, delete,
            group_call
    ):
        if any((join, leave, invite, restrict, unrestrict, ban, unban,
                promote, demote, info, settings, pinned, edit, delete,
                group_call)):
            events_filter = _tl.ChannelAdminLogEventsFilter(
                join=join, leave=leave, invite=invite, ban=restrict,
                unban=unrestrict, kick=ban, unkick=unban, promote=promote,
                demote=demote, info=info, settings=settings, pinned=pinned,
                edit=edit, delete=delete, group_call=group_call
            )
        else:
            events_filter = None

        self.entity = await self.client._get_input_peer(entity)

        admin_list = []
        if admins:
            if not utils.is_list_like(admins):
                admins = (admins,)

            for admin in admins:
                admin_list.append(await self.client._get_input_peer(admin))

        self.request = _tl.fn.channels.GetAdminLog(
            self.entity, q=search or '', min_id=min_id, max_id=max_id,
            limit=0, events_filter=events_filter, admins=admin_list or None
        )

    async def _load_next_chunk(self):
        self.request = dataclasses.replace(self.request, limit=min(self.left, _MAX_ADMIN_LOG_CHUNK_SIZE))
        r = await self.client(self.request)
        entities = {utils.get_peer_id(x): x
                    for x in itertools.chain(r.users, r.chats)}

        self.request = dataclasses.replace(self.request, max_id=min((e.id for e in r.events), default=0))
        for ev in r.events:
            if isinstance(ev.action,
                          _tl.ChannelAdminLogEventActionEditMessage):
                ev = dataclasses.replace(ev, action=dataclasses.replace(
                    ev.action,
                    prev_message=_custom.Message._new(self.client, ev.action.prev_message, entities, self.entity),
                    new_message=_custom.Message._new(self.client, ev.action.new_message, entities, self.entity)
                ))

            elif isinstance(ev.action,
                            _tl.ChannelAdminLogEventActionDeleteMessage):
                ev.action.message = _custom.Message._new(
                    self.client, ev.action.message, entities, self.entity)

            self.buffer.append(_custom.AdminLogEvent(ev, entities))

        if len(r.events) < self.request.limit:
            return True


class _ProfilePhotoIter(requestiter.RequestIter):
    async def _init(
            self, entity, offset, max_id
    ):
        entity = await self.client._get_input_peer(entity)
        ty = helpers._entity_type(entity)
        if ty == helpers._EntityType.USER:
            self.request = _tl.fn.photos.GetUserPhotos(
                entity,
                offset=offset,
                max_id=max_id,
                limit=1
            )
        else:
            self.request = _tl.fn.messages.Search(
                peer=entity,
                q='',
                filter=_tl.InputMessagesFilterChatPhotos(),
                min_date=None,
                max_date=None,
                offset_id=0,
                add_offset=offset,
                limit=1,
                max_id=max_id,
                min_id=0,
                hash=0
            )

        if self.limit == 0:
            self.request = dataclasses.replace(self.request, limit=1)
            result = await self.client(self.request)
            if isinstance(result, _tl.photos.Photos):
                self.total = len(result.photos)
            elif isinstance(result, _tl.messages.Messages):
                self.total = len(result.messages)
            else:
                # Luckily both photosSlice and messages have a count for total
                self.total = getattr(result, 'count', None)

    async def _load_next_chunk(self):
        self.request = dataclasses.replace(self.request, limit=min(self.left, _MAX_PROFILE_PHOTO_CHUNK_SIZE))
        result = await self.client(self.request)

        if isinstance(result, _tl.photos.Photos):
            self.buffer = result.photos
            self.left = len(self.buffer)
            self.total = len(self.buffer)
        elif isinstance(result, _tl.messages.Messages):
            self.buffer = [x.action.photo for x in result.messages
                           if isinstance(x.action, _tl.MessageActionChatEditPhoto)]

            self.left = len(self.buffer)
            self.total = len(self.buffer)
        elif isinstance(result, _tl.photos.PhotosSlice):
            self.buffer = result.photos
            self.total = result.count
            if len(self.buffer) < self.request.limit:
                self.left = len(self.buffer)
            else:
                self.request = dataclasses.replace(self.request, offset=self.request.offset + len(result.photos))
        else:
            # Some broadcast channels have a photo that this request doesn't
            # retrieve for whatever random reason the Telegram server feels.
            #
            # This means the `total` count may be wrong but there's not much
            # that can be done around it (perhaps there are too many photos
            # and this is only a partial result so it's not possible to just
            # use the len of the result).
            self.total = getattr(result, 'count', None)

            # Unconditionally fetch the full channel to obtain this photo and
            # yield it with the rest (unless it's a duplicate).
            seen_id = None
            if isinstance(result, _tl.messages.ChannelMessages):
                channel = await self.client(_tl.fn.channels.GetFullChannel(self.request.peer))
                photo = channel.full_chat.chat_photo
                if isinstance(photo, _tl.Photo):
                    self.buffer.append(photo)
                    seen_id = photo.id

            self.buffer.extend(
                x.action.photo for x in result.messages
                if isinstance(x.action, _tl.MessageActionChatEditPhoto)
                and x.action.photo.id != seen_id
            )

            if len(result.messages) < self.request.limit:
                self.left = len(self.buffer)
            elif result.messages:
                self.request = dataclasses.replace(
                    self.request,
                    add_offset=0,
                    offset_id=result.messages[-1].id
                )


def get_participants(
        self: 'TelegramClient',
        chat: 'hints.DialogLike',
        limit: float = (),
        *,
        search: str = '',
        filter: '_tl.TypeChannelParticipantsFilter' = None) -> _ParticipantsIter:
    return _ParticipantsIter(
        self,
        limit,
        entity=chat,
        filter=filter,
        search=search
    )


def get_admin_log(
        self: 'TelegramClient',
        chat: 'hints.DialogLike',
        limit: float = (),
        *,
        max_id: int = 0,
        min_id: int = 0,
        search: str = None,
        admins: 'hints.DialogsLike' = None,
        join: bool = None,
        leave: bool = None,
        invite: bool = None,
        restrict: bool = None,
        unrestrict: bool = None,
        ban: bool = None,
        unban: bool = None,
        promote: bool = None,
        demote: bool = None,
        info: bool = None,
        settings: bool = None,
        pinned: bool = None,
        edit: bool = None,
        delete: bool = None,
        group_call: bool = None) -> _AdminLogIter:
    return _AdminLogIter(
        self,
        limit,
        entity=chat,
        admins=admins,
        search=search,
        min_id=min_id,
        max_id=max_id,
        join=join,
        leave=leave,
        invite=invite,
        restrict=restrict,
        unrestrict=unrestrict,
        ban=ban,
        unban=unban,
        promote=promote,
        demote=demote,
        info=info,
        settings=settings,
        pinned=pinned,
        edit=edit,
        delete=delete,
        group_call=group_call
    )


def get_profile_photos(
        self: 'TelegramClient',
        profile: 'hints.DialogLike',
        limit: int = (),
        *,
        offset: int = 0,
        max_id: int = 0) -> _ProfilePhotoIter:
    return _ProfilePhotoIter(
        self,
        limit,
        entity=profile,
        offset=offset,
        max_id=max_id
    )


def action(
        self: 'TelegramClient',
        dialog: 'hints.DialogLike',
        action: 'typing.Union[str, _tl.TypeSendMessageAction]',
        *,
        delay: float = 4,
        auto_cancel: bool = True) -> 'typing.Union[_ChatAction, typing.Coroutine]':
    action = _ChatAction._parse(action)

    return _ChatAction(
        self, dialog, action, delay=delay, auto_cancel=auto_cancel)

async def edit_admin(
        self: 'TelegramClient',
        chat: 'hints.DialogLike',
        user: 'hints.DialogLike',
        *,
        change_info: bool = None,
        post_messages: bool = None,
        edit_messages: bool = None,
        delete_messages: bool = None,
        ban_users: bool = None,
        invite_users: bool = None,
        pin_messages: bool = None,
        add_admins: bool = None,
        manage_call: bool = None,
        anonymous: bool = None,
        is_admin: bool = None,
        title: str = None) -> _tl.Updates:
    entity = await self._get_input_peer(chat)
    user = await self._get_input_peer(user)
    ty = helpers._entity_type(user)

    perm_names = (
        'change_info', 'post_messages', 'edit_messages', 'delete_messages',
        'ban_users', 'invite_users', 'pin_messages', 'add_admins',
        'anonymous', 'manage_call',
    )

    ty = helpers._entity_type(entity)
    if ty == helpers._EntityType.CHANNEL:
        # If we try to set these permissions in a megagroup, we
        # would get a RIGHT_FORBIDDEN. However, it makes sense
        # that an admin can post messages, so we want to avoid the error
        if post_messages or edit_messages:
            # TODO get rid of this once sessions cache this information
            if entity.channel_id not in self._megagroup_cache:
                full_entity = await self.get_profile(entity)
                self._megagroup_cache[entity.channel_id] = full_entity.megagroup

            if self._megagroup_cache[entity.channel_id]:
                post_messages = None
                edit_messages = None

        perms = locals()
        return await self(_tl.fn.channels.EditAdmin(entity, user, _tl.ChatAdminRights(**{
            # A permission is its explicit (not-None) value or `is_admin`.
            # This essentially makes `is_admin` be the default value.
            name: perms[name] if perms[name] is not None else is_admin
            for name in perm_names
        }), rank=title or ''))

    elif ty == helpers._EntityType.CHAT:
        # If the user passed any permission in a small
        # group chat, they must be a full admin to have it.
        if is_admin is None:
            is_admin = any(locals()[x] for x in perm_names)

        return await self(_tl.fn.messages.EditChatAdmin(
            entity, user, is_admin=is_admin))

    else:
        raise ValueError(
            'You can only edit permissions in groups and channels')

async def edit_permissions(
        self: 'TelegramClient',
        chat: 'hints.DialogLike',
        user: 'typing.Optional[hints.DialogLike]' = None,
        until_date: 'hints.DateLike' = None,
        *,
        view_messages: bool = True,
        send_messages: bool = True,
        send_media: bool = True,
        send_stickers: bool = True,
        send_gifs: bool = True,
        send_games: bool = True,
        send_inline: bool = True,
        embed_link_previews: bool = True,
        send_polls: bool = True,
        change_info: bool = True,
        invite_users: bool = True,
        pin_messages: bool = True) -> _tl.Updates:
    entity = await self._get_input_peer(chat)
    ty = helpers._entity_type(entity)

    rights = _tl.ChatBannedRights(
        until_date=until_date,
        view_messages=not view_messages,
        send_messages=not send_messages,
        send_media=not send_media,
        send_stickers=not send_stickers,
        send_gifs=not send_gifs,
        send_games=not send_games,
        send_inline=not send_inline,
        embed_links=not embed_link_previews,
        send_polls=not send_polls,
        change_info=not change_info,
        invite_users=not invite_users,
        pin_messages=not pin_messages
    )

    if user is None:
        return await self(_tl.fn.messages.EditChatDefaultBannedRights(
            peer=entity,
            banned_rights=rights
        ))

    user = await self._get_input_peer(user)

    if isinstance(user, _tl.InputPeerSelf):
        raise ValueError('You cannot restrict yourself')

    return await self(_tl.fn.channels.EditBanned(
        channel=entity,
        participant=user,
        banned_rights=rights
    ))

async def kick_participant(
        self: 'TelegramClient',
        chat: 'hints.DialogLike',
        user: 'typing.Optional[hints.DialogLike]'
):
    entity = await self._get_input_peer(chat)
    user = await self._get_input_peer(user)

    ty = helpers._entity_type(entity)
    if ty == helpers._EntityType.CHAT:
        resp = await self(_tl.fn.messages.DeleteChatUser(entity.chat_id, user))
    elif ty == helpers._EntityType.CHANNEL:
        if isinstance(user, _tl.InputPeerSelf):
            # Despite no longer being in the channel, the account still
            # seems to get the service message.
            resp = await self(_tl.fn.channels.LeaveChannel(entity))
        else:
            resp = await self(_tl.fn.channels.EditBanned(
                channel=entity,
                participant=user,
                banned_rights=_tl.ChatBannedRights(
                    until_date=None, view_messages=True)
            ))
            await asyncio.sleep(0.5)
            await self(_tl.fn.channels.EditBanned(
                channel=entity,
                participant=user,
                banned_rights=_tl.ChatBannedRights(until_date=None)
            ))
    else:
        raise ValueError('You must pass either a channel or a chat')

    return self._get_response_message(None, resp, entity)

async def get_permissions(
        self: 'TelegramClient',
        chat: 'hints.DialogLike',
        user: 'hints.DialogLike' = None
) -> 'typing.Optional[_custom.ParticipantPermissions]':
    entity = await self.get_profile(chat)

    if not user:
        if helpers._entity_type(entity) != helpers._EntityType.USER:
            return entity.default_banned_rights

    entity = await self._get_input_peer(entity)
    user = await self._get_input_peer(user)

    if helpers._entity_type(entity) == helpers._EntityType.CHANNEL:
        participant = await self(_tl.fn.channels.GetParticipant(
            entity,
            user
        ))
        return _custom.ParticipantPermissions(participant.participant, False)
    elif helpers._entity_type(entity) == helpers._EntityType.CHAT:
        chat = await self(_tl.fn.messages.GetFullChat(
            entity
        ))
        if isinstance(user, _tl.InputPeerSelf):
            user = _tl.PeerUser(self._session_state.user_id)
        for participant in chat.full_chat.participants.participants:
            if participant.user_id == user.user_id:
                return _custom.ParticipantPermissions(participant, True)
        raise errors.USER_NOT_PARTICIPANT(400, 'USER_NOT_PARTICIPANT')

    raise ValueError('You must pass either a channel or a chat')

async def get_stats(
        self: 'TelegramClient',
        chat: 'hints.DialogLike',
        message: 'typing.Union[int, _tl.Message]' = None,
):
    entity = await self._get_input_peer(chat)

    message = utils.get_message_id(message)
    if message is not None:
        try:
            req = _tl.fn.stats.GetMessageStats(entity, message)
            return await self(req)
        except errors.STATS_MIGRATE as e:
            dc = e.dc
    else:
        # Don't bother fetching the Channel entity (costs a request), instead
        # try to guess and if it fails we know it's the other one (best case
        # no extra request, worst just one).
        try:
            req = _tl.fn.stats.GetBroadcastStats(entity)
            return await self(req)
        except errors.STATS_MIGRATE as e:
            dc = e.dc
        except errors.BROADCAST_REQUIRED:
            req = _tl.fn.stats.GetMegagroupStats(entity)
            try:
                return await self(req)
            except errors.STATS_MIGRATE as e:
                dc = e.dc

    sender = await self._borrow_exported_sender(dc)
    try:
        # req will be resolved to use the right types inside by now
        return await sender.send(req)
    finally:
        await self._return_exported_sender(sender)
