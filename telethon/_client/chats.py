import asyncio
import inspect
import itertools
import string
import typing

from .. import helpers, utils, hints, errors
from ..requestiter import RequestIter
from ..tl import types, functions, custom

if typing.TYPE_CHECKING:
    from .telegramclient import TelegramClient

_MAX_PARTICIPANTS_CHUNK_SIZE = 200
_MAX_ADMIN_LOG_CHUNK_SIZE = 100
_MAX_PROFILE_PHOTO_CHUNK_SIZE = 100


class _ChatAction:
    _str_mapping = {
        'typing': types.SendMessageTypingAction(),
        'contact': types.SendMessageChooseContactAction(),
        'game': types.SendMessageGamePlayAction(),
        'location': types.SendMessageGeoLocationAction(),
        'sticker': types.SendMessageChooseStickerAction(),

        'record-audio': types.SendMessageRecordAudioAction(),
        'record-voice': types.SendMessageRecordAudioAction(),  # alias
        'record-round': types.SendMessageRecordRoundAction(),
        'record-video': types.SendMessageRecordVideoAction(),

        'audio': types.SendMessageUploadAudioAction(1),
        'voice': types.SendMessageUploadAudioAction(1),  # alias
        'song': types.SendMessageUploadAudioAction(1),  # alias
        'round': types.SendMessageUploadRoundAction(1),
        'video': types.SendMessageUploadVideoAction(1),

        'photo': types.SendMessageUploadPhotoAction(1),
        'document': types.SendMessageUploadDocumentAction(1),
        'file': types.SendMessageUploadDocumentAction(1),  # alias

        'cancel': types.SendMessageCancelAction()
    }

    def __init__(self, client, chat, action, *, delay, auto_cancel):
        self._client = client
        self._chat = chat
        self._action = action
        self._delay = delay
        self._auto_cancel = auto_cancel
        self._request = None
        self._task = None
        self._running = False

    async def __aenter__(self):
        self._chat = await self._client.get_input_entity(self._chat)

        # Since `self._action` is passed by reference we can avoid
        # recreating the request all the time and still modify
        # `self._action.progress` directly in `progress`.
        self._request = functions.messages.SetTypingRequest(
            self._chat, self._action)

        self._running = True
        self._task = self._client.loop.create_task(self._update())
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

    __enter__ = helpers._sync_enter
    __exit__ = helpers._sync_exit

    async def _update(self):
        try:
            while self._running:
                await self._client(self._request)
                await asyncio.sleep(self._delay)
        except ConnectionError:
            pass
        except asyncio.CancelledError:
            if self._auto_cancel:
                await self._client(functions.messages.SetTypingRequest(
                    self._chat, types.SendMessageCancelAction()))

    def progress(self, current, total):
        if hasattr(self._action, 'progress'):
            self._action.progress = 100 * round(current / total)


class _ParticipantsIter(RequestIter):
    async def _init(self, entity, filter, search, aggressive):
        if isinstance(filter, type):
            if filter in (types.ChannelParticipantsBanned,
                          types.ChannelParticipantsKicked,
                          types.ChannelParticipantsSearch,
                          types.ChannelParticipantsContacts):
                # These require a `q` parameter (support types for convenience)
                filter = filter('')
            else:
                filter = filter()

        entity = await self.client.get_input_entity(entity)
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

        # Only used for channels, but we should always set the attribute
        self.requests = []

        if ty == helpers._EntityType.CHANNEL:
            if self.limit <= 0:
                # May not have access to the channel, but getFull can get the .total.
                self.total = (await self.client(
                    functions.channels.GetFullChannelRequest(entity)
                )).full_chat.participants_count
                raise StopAsyncIteration

            self.seen = set()
            if aggressive and not filter:
                self.requests.extend(functions.channels.GetParticipantsRequest(
                    channel=entity,
                    filter=types.ChannelParticipantsSearch(x),
                    offset=0,
                    limit=_MAX_PARTICIPANTS_CHUNK_SIZE,
                    hash=0
                ) for x in (search or string.ascii_lowercase))
            else:
                self.requests.append(functions.channels.GetParticipantsRequest(
                    channel=entity,
                    filter=filter or types.ChannelParticipantsSearch(search),
                    offset=0,
                    limit=_MAX_PARTICIPANTS_CHUNK_SIZE,
                    hash=0
                ))

        elif ty == helpers._EntityType.CHAT:
            full = await self.client(
                functions.messages.GetFullChatRequest(entity.chat_id))
            if not isinstance(
                    full.full_chat.participants, types.ChatParticipants):
                # ChatParticipantsForbidden won't have ``.participants``
                self.total = 0
                raise StopAsyncIteration

            self.total = len(full.full_chat.participants.participants)

            users = {user.id: user for user in full.users}
            for participant in full.full_chat.participants.participants:
                if isinstance(participant, types.ChannelParticipantBanned):
                    user_id = participant.peer.user_id
                else:
                    user_id = participant.user_id
                user = users[user_id]
                if not self.filter_entity(user):
                    continue

                user = users[user_id]
                user.participant = participant
                self.buffer.append(user)

            return True
        else:
            self.total = 1
            if self.limit != 0:
                user = await self.client.get_entity(entity)
                if self.filter_entity(user):
                    user.participant = None
                    self.buffer.append(user)

            return True

    async def _load_next_chunk(self):
        if not self.requests:
            return True

        # Only care about the limit for the first request
        # (small amount of people, won't be aggressive).
        #
        # Most people won't care about getting exactly 12,345
        # members so it doesn't really matter not to be 100%
        # precise with being out of the offset/limit here.
        self.requests[0].limit = min(
            self.limit - self.requests[0].offset, _MAX_PARTICIPANTS_CHUNK_SIZE)

        if self.requests[0].offset > self.limit:
            return True

        if self.total is None:
            f = self.requests[0].filter
            if len(self.requests) > 1 or (
                not isinstance(f, types.ChannelParticipantsRecent)
                and (not isinstance(f, types.ChannelParticipantsSearch) or f.q)
            ):
                # Only do an additional getParticipants here to get the total
                # if there's a filter which would reduce the real total number.
                # getParticipants is cheaper than getFull.
                self.total = (await self.client(functions.channels.GetParticipantsRequest(
                    channel=self.requests[0].channel,
                    filter=types.ChannelParticipantsRecent(),
                    offset=0,
                    limit=1,
                    hash=0
                ))).count

        results = await self.client(self.requests)
        for i in reversed(range(len(self.requests))):
            participants = results[i]
            if self.total is None:
                # Will only get here if there was one request with a filter that matched all users.
                self.total = participants.count
            if not participants.users:
                self.requests.pop(i)
                continue

            self.requests[i].offset += len(participants.participants)
            users = {user.id: user for user in participants.users}
            for participant in participants.participants:

                if isinstance(participant, types.ChannelParticipantBanned):
                    if not isinstance(participant.peer, types.PeerUser):
                        # May have the entire channel banned. See #3105.
                        continue
                    user_id = participant.peer.user_id
                else:
                    user_id = participant.user_id

                user = users[user_id]
                if not self.filter_entity(user) or user.id in self.seen:
                    continue
                self.seen.add(user_id)
                user = users[user_id]
                user.participant = participant
                self.buffer.append(user)


class _AdminLogIter(RequestIter):
    async def _init(
            self, entity, admins, search, min_id, max_id,
            join, leave, invite, restrict, unrestrict, ban, unban,
            promote, demote, info, settings, pinned, edit, delete,
            group_call
    ):
        if any((join, leave, invite, restrict, unrestrict, ban, unban,
                promote, demote, info, settings, pinned, edit, delete,
                group_call)):
            events_filter = types.ChannelAdminLogEventsFilter(
                join=join, leave=leave, invite=invite, ban=restrict,
                unban=unrestrict, kick=ban, unkick=unban, promote=promote,
                demote=demote, info=info, settings=settings, pinned=pinned,
                edit=edit, delete=delete, group_call=group_call
            )
        else:
            events_filter = None

        self.entity = await self.client.get_input_entity(entity)

        admin_list = []
        if admins:
            if not utils.is_list_like(admins):
                admins = (admins,)

            for admin in admins:
                admin_list.append(await self.client.get_input_entity(admin))

        self.request = functions.channels.GetAdminLogRequest(
            self.entity, q=search or '', min_id=min_id, max_id=max_id,
            limit=0, events_filter=events_filter, admins=admin_list or None
        )

    async def _load_next_chunk(self):
        self.request.limit = min(self.left, _MAX_ADMIN_LOG_CHUNK_SIZE)
        r = await self.client(self.request)
        entities = {utils.get_peer_id(x): x
                    for x in itertools.chain(r.users, r.chats)}

        self.request.max_id = min((e.id for e in r.events), default=0)
        for ev in r.events:
            if isinstance(ev.action,
                          types.ChannelAdminLogEventActionEditMessage):
                ev.action.prev_message._finish_init(
                    self.client, entities, self.entity)

                ev.action.new_message._finish_init(
                    self.client, entities, self.entity)

            elif isinstance(ev.action,
                            types.ChannelAdminLogEventActionDeleteMessage):
                ev.action.message._finish_init(
                    self.client, entities, self.entity)

            self.buffer.append(custom.AdminLogEvent(ev, entities))

        if len(r.events) < self.request.limit:
            return True


class _ProfilePhotoIter(RequestIter):
    async def _init(
            self, entity, offset, max_id
    ):
        entity = await self.client.get_input_entity(entity)
        ty = helpers._entity_type(entity)
        if ty == helpers._EntityType.USER:
            self.request = functions.photos.GetUserPhotosRequest(
                entity,
                offset=offset,
                max_id=max_id,
                limit=1
            )
        else:
            self.request = functions.messages.SearchRequest(
                peer=entity,
                q='',
                filter=types.InputMessagesFilterChatPhotos(),
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
            self.request.limit = 1
            result = await self.client(self.request)
            if isinstance(result, types.photos.Photos):
                self.total = len(result.photos)
            elif isinstance(result, types.messages.Messages):
                self.total = len(result.messages)
            else:
                # Luckily both photosSlice and messages have a count for total
                self.total = getattr(result, 'count', None)

    async def _load_next_chunk(self):
        self.request.limit = min(self.left, _MAX_PROFILE_PHOTO_CHUNK_SIZE)
        result = await self.client(self.request)

        if isinstance(result, types.photos.Photos):
            self.buffer = result.photos
            self.left = len(self.buffer)
            self.total = len(self.buffer)
        elif isinstance(result, types.messages.Messages):
            self.buffer = [x.action.photo for x in result.messages
                           if isinstance(x.action, types.MessageActionChatEditPhoto)]

            self.left = len(self.buffer)
            self.total = len(self.buffer)
        elif isinstance(result, types.photos.PhotosSlice):
            self.buffer = result.photos
            self.total = result.count
            if len(self.buffer) < self.request.limit:
                self.left = len(self.buffer)
            else:
                self.request.offset += len(result.photos)
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
            if isinstance(result, types.messages.ChannelMessages):
                channel = await self.client(functions.channels.GetFullChannelRequest(self.request.peer))
                photo = channel.full_chat.chat_photo
                if isinstance(photo, types.Photo):
                    self.buffer.append(photo)
                    seen_id = photo.id

            self.buffer.extend(
                x.action.photo for x in result.messages
                if isinstance(x.action, types.MessageActionChatEditPhoto)
                and x.action.photo.id != seen_id
            )

            if len(result.messages) < self.request.limit:
                self.left = len(self.buffer)
            elif result.messages:
                self.request.add_offset = 0
                self.request.offset_id = result.messages[-1].id


def iter_participants(
        self: 'TelegramClient',
        entity: 'hints.EntityLike',
        limit: float = None,
        *,
        search: str = '',
        filter: 'types.TypeChannelParticipantsFilter' = None,
        aggressive: bool = False) -> _ParticipantsIter:
    return _ParticipantsIter(
        self,
        limit,
        entity=entity,
        filter=filter,
        search=search,
        aggressive=aggressive
    )

async def get_participants(
        self: 'TelegramClient',
        *args,
        **kwargs) -> 'hints.TotalList':
    return await self.iter_participants(*args, **kwargs).collect()


def iter_admin_log(
        self: 'TelegramClient',
        entity: 'hints.EntityLike',
        limit: float = None,
        *,
        max_id: int = 0,
        min_id: int = 0,
        search: str = None,
        admins: 'hints.EntitiesLike' = None,
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
        entity=entity,
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

async def get_admin_log(
        self: 'TelegramClient',
        *args,
        **kwargs) -> 'hints.TotalList':
    return await self.iter_admin_log(*args, **kwargs).collect()


def iter_profile_photos(
        self: 'TelegramClient',
        entity: 'hints.EntityLike',
        limit: int = None,
        *,
        offset: int = 0,
        max_id: int = 0) -> _ProfilePhotoIter:
    return _ProfilePhotoIter(
        self,
        limit,
        entity=entity,
        offset=offset,
        max_id=max_id
    )

async def get_profile_photos(
        self: 'TelegramClient',
        *args,
        **kwargs) -> 'hints.TotalList':
    return await self.iter_profile_photos(*args, **kwargs).collect()


def action(
        self: 'TelegramClient',
        entity: 'hints.EntityLike',
        action: 'typing.Union[str, types.TypeSendMessageAction]',
        *,
        delay: float = 4,
        auto_cancel: bool = True) -> 'typing.Union[_ChatAction, typing.Coroutine]':
    if isinstance(action, str):
        try:
            action = _ChatAction._str_mapping[action.lower()]
        except KeyError:
            raise ValueError(
                'No such action "{}"'.format(action)) from None
    elif not isinstance(action, types.TLObject) or action.SUBCLASS_OF_ID != 0x20b2cc21:
        # 0x20b2cc21 = crc32(b'SendMessageAction')
        if isinstance(action, type):
            raise ValueError('You must pass an instance, not the class')
        else:
            raise ValueError('Cannot use {} as action'.format(action))

    if isinstance(action, types.SendMessageCancelAction):
        # ``SetTypingRequest.resolve`` will get input peer of ``entity``.
        return self(functions.messages.SetTypingRequest(
            entity, types.SendMessageCancelAction()))

    return _ChatAction(
        self, entity, action, delay=delay, auto_cancel=auto_cancel)

async def edit_admin(
        self: 'TelegramClient',
        entity: 'hints.EntityLike',
        user: 'hints.EntityLike',
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
        title: str = None) -> types.Updates:
    entity = await self.get_input_entity(entity)
    user = await self.get_input_entity(user)
    ty = helpers._entity_type(user)
    if ty != helpers._EntityType.USER:
        raise ValueError('You must pass a user entity')

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
                full_entity = await self.get_entity(entity)
                self._megagroup_cache[entity.channel_id] = full_entity.megagroup

            if self._megagroup_cache[entity.channel_id]:
                post_messages = None
                edit_messages = None

        perms = locals()
        return await self(functions.channels.EditAdminRequest(entity, user, types.ChatAdminRights(**{
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

        return await self(functions.messages.EditChatAdminRequest(
            entity, user, is_admin=is_admin))

    else:
        raise ValueError(
            'You can only edit permissions in groups and channels')

async def edit_permissions(
        self: 'TelegramClient',
        entity: 'hints.EntityLike',
        user: 'typing.Optional[hints.EntityLike]' = None,
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
        pin_messages: bool = True) -> types.Updates:
    entity = await self.get_input_entity(entity)
    ty = helpers._entity_type(entity)
    if ty != helpers._EntityType.CHANNEL:
        raise ValueError('You must pass either a channel or a supergroup')

    rights = types.ChatBannedRights(
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
        return await self(functions.messages.EditChatDefaultBannedRightsRequest(
            peer=entity,
            banned_rights=rights
        ))

    user = await self.get_input_entity(user)
    ty = helpers._entity_type(user)
    if ty != helpers._EntityType.USER:
        raise ValueError('You must pass a user entity')

    if isinstance(user, types.InputPeerSelf):
        raise ValueError('You cannot restrict yourself')

    return await self(functions.channels.EditBannedRequest(
        channel=entity,
        participant=user,
        banned_rights=rights
    ))

async def kick_participant(
        self: 'TelegramClient',
        entity: 'hints.EntityLike',
        user: 'typing.Optional[hints.EntityLike]'
):
    entity = await self.get_input_entity(entity)
    user = await self.get_input_entity(user)
    if helpers._entity_type(user) != helpers._EntityType.USER:
        raise ValueError('You must pass a user entity')

    ty = helpers._entity_type(entity)
    if ty == helpers._EntityType.CHAT:
        resp = await self(functions.messages.DeleteChatUserRequest(entity.chat_id, user))
    elif ty == helpers._EntityType.CHANNEL:
        if isinstance(user, types.InputPeerSelf):
            # Despite no longer being in the channel, the account still
            # seems to get the service message.
            resp = await self(functions.channels.LeaveChannelRequest(entity))
        else:
            resp = await self(functions.channels.EditBannedRequest(
                channel=entity,
                participant=user,
                banned_rights=types.ChatBannedRights(
                    until_date=None, view_messages=True)
            ))
            await asyncio.sleep(0.5)
            await self(functions.channels.EditBannedRequest(
                channel=entity,
                participant=user,
                banned_rights=types.ChatBannedRights(until_date=None)
            ))
    else:
        raise ValueError('You must pass either a channel or a chat')

    return self._get_response_message(None, resp, entity)

async def get_permissions(
        self: 'TelegramClient',
        entity: 'hints.EntityLike',
        user: 'hints.EntityLike' = None
) -> 'typing.Optional[custom.ParticipantPermissions]':
    entity = await self.get_entity(entity)

    if not user:
        if isinstance(entity, types.Channel):
            FullChat = await self(functions.channels.GetFullChannelRequest(entity))
        elif isinstance(entity, types.Chat):
            FullChat = await self(functions.messages.GetFullChatRequest(entity))
        else:
            return
        return FullChat.chats[0].default_banned_rights

    entity = await self.get_input_entity(entity)
    user = await self.get_input_entity(user)
    if helpers._entity_type(user) != helpers._EntityType.USER:
        raise ValueError('You must pass a user entity')
    if helpers._entity_type(entity) == helpers._EntityType.CHANNEL:
        participant = await self(functions.channels.GetParticipantRequest(
            entity,
            user
        ))
        return custom.ParticipantPermissions(participant.participant, False)
    elif helpers._entity_type(entity) == helpers._EntityType.CHAT:
        chat = await self(functions.messages.GetFullChatRequest(
            entity
        ))
        if isinstance(user, types.InputPeerSelf):
            user = await self.get_me(input_peer=True)
        for participant in chat.full_chat.participants.participants:
            if participant.user_id == user.user_id:
                return custom.ParticipantPermissions(participant, True)
        raise errors.UserNotParticipantError(None)

    raise ValueError('You must pass either a channel or a chat')

async def get_stats(
        self: 'TelegramClient',
        entity: 'hints.EntityLike',
        message: 'typing.Union[int, types.Message]' = None,
):
    entity = await self.get_input_entity(entity)
    if helpers._entity_type(entity) != helpers._EntityType.CHANNEL:
        raise TypeError('You must pass a channel entity')

    message = utils.get_message_id(message)
    if message is not None:
        try:
            req = functions.stats.GetMessageStatsRequest(entity, message)
            return await self(req)
        except errors.StatsMigrateError as e:
            dc = e.dc
    else:
        # Don't bother fetching the Channel entity (costs a request), instead
        # try to guess and if it fails we know it's the other one (best case
        # no extra request, worst just one).
        try:
            req = functions.stats.GetBroadcastStatsRequest(entity)
            return await self(req)
        except errors.StatsMigrateError as e:
            dc = e.dc
        except errors.BroadcastRequiredError:
            req = functions.stats.GetMegagroupStatsRequest(entity)
            try:
                return await self(req)
            except errors.StatsMigrateError as e:
                dc = e.dc

    sender = await self._borrow_exported_sender(dc)
    try:
        # req will be resolved to use the right types inside by now
        return await sender.send(req)
    finally:
        await self._return_exported_sender(sender)
