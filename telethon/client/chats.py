import asyncio
import inspect
import itertools
import string
import typing

from .. import helpers, utils, hints
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

        'record-audio': types.SendMessageRecordAudioAction(),
        'record-voice': types.SendMessageRecordAudioAction(),  # alias
        'record-round': types.SendMessageRecordRoundAction(),
        'record-video': types.SendMessageRecordVideoAction(),

        'audio': types.SendMessageUploadAudioAction(1),
        'voice': types.SendMessageUploadAudioAction(1),  # alias
        'round': types.SendMessageUploadRoundAction(1),
        'video': types.SendMessageUploadVideoAction(1),

        'photo': types.SendMessageUploadPhotoAction(1),
        'document': types.SendMessageUploadDocumentAction(1),
        'file': types.SendMessageUploadDocumentAction(1),  # alias
        'song': types.SendMessageUploadDocumentAction(1),  # alias

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
        if search and (filter
                       or not isinstance(entity, types.InputPeerChannel)):
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

        if isinstance(entity, types.InputPeerChannel):
            self.total = (await self.client(
                functions.channels.GetFullChannelRequest(entity)
            )).full_chat.participants_count

            if self.limit <= 0:
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

        elif isinstance(entity, types.InputPeerChat):
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
                user = users[participant.user_id]
                if not self.filter_entity(user):
                    continue

                user = users[participant.user_id]
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

        results = await self.client(self.requests)
        for i in reversed(range(len(self.requests))):
            participants = results[i]
            if not participants.users:
                self.requests.pop(i)
                continue

            self.requests[i].offset += len(participants.participants)
            users = {user.id: user for user in participants.users}
            for participant in participants.participants:
                user = users[participant.user_id]
                if not self.filter_entity(user) or user.id in self.seen:
                    continue

                self.seen.add(participant.user_id)
                user = users[participant.user_id]
                user.participant = participant
                self.buffer.append(user)


class _AdminLogIter(RequestIter):
    async def _init(
            self, entity, admins, search, min_id, max_id,
            join, leave, invite, restrict, unrestrict, ban, unban,
            promote, demote, info, settings, pinned, edit, delete
    ):
        if any((join, leave, invite, restrict, unrestrict, ban, unban,
                promote, demote, info, settings, pinned, edit, delete)):
            events_filter = types.ChannelAdminLogEventsFilter(
                join=join, leave=leave, invite=invite, ban=restrict,
                unban=unrestrict, kick=ban, unkick=unban, promote=promote,
                demote=demote, info=info, settings=settings, pinned=pinned,
                edit=edit, delete=delete
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
        if isinstance(entity, (types.InputPeerUser, types.InputPeerSelf)):
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
            self.buffer = [x.action.photo for x in result.messages
                           if isinstance(x.action, types.MessageActionChatEditPhoto)]
            self.total = getattr(result, 'count', None)
            if len(result.messages) < self.request.limit:
                self.left = len(self.buffer)
            elif result.messages:
                self.request.add_offset = 0
                self.request.offset_id = result.messages[-1].id


class ChatMethods:

    # region Public methods

    def iter_participants(
            self: 'TelegramClient',
            entity: 'hints.EntityLike',
            limit: float = None,
            *,
            search: str = '',
            filter: 'types.TypeChannelParticipantsFilter' = None,
            aggressive: bool = False) -> _ParticipantsIter:
        """
        Iterator over the participants belonging to the specified chat.

        The order is unspecified.

        Arguments
            entity (`entity`):
                The entity from which to retrieve the participants list.

            limit (`int`):
                Limits amount of participants fetched.

            search (`str`, optional):
                Look for participants with this string in name/username.

                If ``aggressive is True``, the symbols from this string will
                be used.

            filter (:tl:`ChannelParticipantsFilter`, optional):
                The filter to be used, if you want e.g. only admins
                Note that you might not have permissions for some filter.
                This has no effect for normal chats or users.

                .. note::

                    The filter :tl:`ChannelParticipantsBanned` will return
                    *restricted* users. If you want *banned* users you should
                    use :tl:`ChannelParticipantsKicked` instead.

            aggressive (`bool`, optional):
                Aggressively looks for all participants in the chat.

                This is useful for channels since 20 July 2018,
                Telegram added a server-side limit where only the
                first 200 members can be retrieved. With this flag
                set, more than 200 will be often be retrieved.

                This has no effect if a ``filter`` is given.

        Yields
            The :tl:`User` objects returned by :tl:`GetParticipantsRequest`
            with an additional ``.participant`` attribute which is the
            matched :tl:`ChannelParticipant` type for channels/megagroups
            or :tl:`ChatParticipants` for normal chats.

        Example
            .. code-block:: python

                # Show all user IDs in a chat
                async for user in client.iter_participants(chat):
                    print(user.id)

                # Search by name
                async for user in client.iter_participants(chat, search='name'):
                    print(user.username)

                # Filter by admins
                from telethon.tl.types import ChannelParticipantsAdmins
                async for user in client.iter_participants(chat, filter=ChannelParticipantsAdmins):
                    print(user.first_name)
        """
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
        """
        Same as `iter_participants()`, but returns a
        `TotalList <telethon.helpers.TotalList>` instead.

        Example
            .. code-block:: python

                users = await client.get_participants(chat)
                print(users[0].first_name)

                for user in users:
                    if user.username is not None:
                        print(user.username)
        """
        return await self.iter_participants(*args, **kwargs).collect()

    get_participants.__signature__ = inspect.signature(iter_participants)

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
            delete: bool = None) -> _AdminLogIter:
        """
        Iterator over the admin log for the specified channel.

        The default order is from the most recent event to to the oldest.

        Note that you must be an administrator of it to use this method.

        If none of the filters are present (i.e. they all are `None`),
        *all* event types will be returned. If at least one of them is
        `True`, only those that are true will be returned.

        Arguments
            entity (`entity`):
                The channel entity from which to get its admin log.

            limit (`int` | `None`, optional):
                Number of events to be retrieved.

                The limit may also be `None`, which would eventually return
                the whole history.

            max_id (`int`):
                All the events with a higher (newer) ID or equal to this will
                be excluded.

            min_id (`int`):
                All the events with a lower (older) ID or equal to this will
                be excluded.

            search (`str`):
                The string to be used as a search query.

            admins (`entity` | `list`):
                If present, the events will be filtered by these admins
                (or single admin) and only those caused by them will be
                returned.

            join (`bool`):
                If `True`, events for when a user joined will be returned.

            leave (`bool`):
                If `True`, events for when a user leaves will be returned.

            invite (`bool`):
                If `True`, events for when a user joins through an invite
                link will be returned.

            restrict (`bool`):
                If `True`, events with partial restrictions will be
                returned. This is what the API calls "ban".

            unrestrict (`bool`):
                If `True`, events removing restrictions will be returned.
                This is what the API calls "unban".

            ban (`bool`):
                If `True`, events applying or removing all restrictions will
                be returned. This is what the API calls "kick" (restricting
                all permissions removed is a ban, which kicks the user).

            unban (`bool`):
                If `True`, events removing all restrictions will be
                returned. This is what the API calls "unkick".

            promote (`bool`):
                If `True`, events with admin promotions will be returned.

            demote (`bool`):
                If `True`, events with admin demotions will be returned.

            info (`bool`):
                If `True`, events changing the group info will be returned.

            settings (`bool`):
                If `True`, events changing the group settings will be
                returned.

            pinned (`bool`):
                If `True`, events of new pinned messages will be returned.

            edit (`bool`):
                If `True`, events of message edits will be returned.

            delete (`bool`):
                If `True`, events of message deletions will be returned.

        Yields
            Instances of `AdminLogEvent <telethon.tl.custom.adminlogevent.AdminLogEvent>`.

        Example
            .. code-block:: python

                async for event in client.iter_admin_log(channel):
                    if event.changed_title:
                        print('The title changed from', event.old, 'to', event.new)
        """
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
            delete=delete
        )

    async def get_admin_log(
            self: 'TelegramClient',
            *args,
            **kwargs) -> 'hints.TotalList':
        """
        Same as `iter_admin_log()`, but returns a ``list`` instead.

        Example
            .. code-block:: python

                # Get a list of deleted message events which said "heck"
                events = await client.get_admin_log(channel, search='heck', delete=True)

                # Print the old message before it was deleted
                print(events[0].old)
        """
        return await self.iter_admin_log(*args, **kwargs).collect()

    get_admin_log.__signature__ = inspect.signature(iter_admin_log)

    def iter_profile_photos(
            self: 'TelegramClient',
            entity: 'hints.EntityLike',
            limit: int = None,
            *,
            offset: int = 0,
            max_id: int = 0) -> _ProfilePhotoIter:
        """
        Iterator over a user's profile photos or a chat's photos.

        The order is from the most recent photo to the oldest.

        Arguments
            entity (`entity`):
                The entity from which to get the profile or chat photos.

            limit (`int` | `None`, optional):
                Number of photos to be retrieved.

                The limit may also be `None`, which would eventually all
                the photos that are still available.

            offset (`int`):
                How many photos should be skipped before returning the first one.

            max_id (`int`):
                The maximum ID allowed when fetching photos.

        Yields
            Instances of :tl:`Photo`.

        Example
            .. code-block:: python

                # Download all the profile photos of some user
                async for photo in client.iter_profile_photos(user):
                    await client.download_media(photo)
        """
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
        """
        Same as `iter_profile_photos()`, but returns a
        `TotalList <telethon.helpers.TotalList>` instead.

        Example
            .. code-block:: python

                # Get the photos of a channel
                photos = await client.get_profile_photos(channel)

                # Download the oldest photo
                await client.download_media(photos[-1])
        """
        return await self.iter_profile_photos(*args, **kwargs).collect()

    get_profile_photos.__signature__ = inspect.signature(iter_profile_photos)

    def action(
            self: 'TelegramClient',
            entity: 'hints.EntityLike',
            action: 'typing.Union[str, types.TypeSendMessageAction]',
            *,
            delay: float = 4,
            auto_cancel: bool = True) -> 'typing.Union[_ChatAction, typing.Coroutine]':
        """
        Returns a context-manager object to represent a "chat action".

        Chat actions indicate things like "user is typing", "user is
        uploading a photo", etc.

        If the action is ``'cancel'``, you should just ``await`` the result,
        since it makes no sense to use a context-manager for it.

        See the example below for intended usage.

        Arguments
            entity (`entity`):
                The entity where the action should be showed in.

            action (`str` | :tl:`SendMessageAction`):
                The action to show. You can either pass a instance of
                :tl:`SendMessageAction` or better, a string used while:

                * ``'typing'``: typing a text message.
                * ``'contact'``: choosing a contact.
                * ``'game'``: playing a game.
                * ``'location'``: choosing a geo location.
                * ``'record-audio'``: recording a voice note.
                  You may use ``'record-voice'`` as alias.
                * ``'record-round'``: recording a round video.
                * ``'record-video'``: recording a normal video.
                * ``'audio'``: sending an audio file (voice note or song).
                  You may use ``'voice'`` and ``'song'`` as aliases.
                * ``'round'``: uploading a round video.
                * ``'video'``: uploading a video file.
                * ``'photo'``: uploading a photo.
                * ``'document'``: uploading a document file.
                  You may use ``'file'`` as alias.
                * ``'cancel'``: cancel any pending action in this chat.

                Invalid strings will raise a ``ValueError``.

            delay (`int` | `float`):
                The delay, in seconds, to wait between sending actions.
                For example, if the delay is 5 and it takes 7 seconds to
                do something, three requests will be made at 0s, 5s, and
                7s to cancel the action.

            auto_cancel (`bool`):
                Whether the action should be cancelled once the context
                manager exists or not. The default is `True`, since
                you don't want progress to be shown when it has already
                completed.

        Returns
            Either a context-manager object or a coroutine.

        Example
            .. code-block:: python

                # Type for 2 seconds, then send a message
                async with client.action(chat, 'typing'):
                    await asyncio.sleep(2)
                    await client.send_message(chat, 'Hello world! I type slow ^^')

                # Cancel any previous action
                await client.action(chat, 'cancel')

                # Upload a document, showing its progress (most clients ignore this)
                async with client.action(chat, 'document') as action:
                    await client.send_file(chat, zip_file, progress_callback=action.progress)
        """
        if isinstance(action, str):
            try:
                action = _ChatAction._str_mapping[action.lower()]
            except KeyError:
                raise ValueError('No such action "{}"'.format(action)) from None
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
            is_admin: bool = None,
            title: str = None) -> types.Updates:
        """
        Edits admin permissions for someone in a chat.

        Raises an error if a wrong combination of rights are given
        (e.g. you don't have enough permissions to grant one).

        Unless otherwise stated, permissions will work in channels and megagroups.

        Arguments
            entity (`entity`):
                The channel, megagroup or chat where the promotion should happen.

            user (`entity`):
                The user to be promoted.

            change_info (`bool`, optional):
                Whether the user will be able to change info.

            post_messages (`bool`, optional):
                Whether the user will be able to post in the channel.
                This will only work in broadcast channels.

            edit_messages (`bool`, optional):
                Whether the user will be able to edit messages in the channel.
                This will only work in broadcast channels.

            delete_messages (`bool`, optional):
                Whether the user will be able to delete messages.

            ban_users (`bool`, optional):
                Whether the user will be able to ban users.

            invite_users (`bool`, optional):
                Whether the user will be able to invite users. Needs some testing.

            pin_messages (`bool`, optional):
                Whether the user will be able to pin messages.

            add_admins (`bool`, optional):
                Whether the user will be able to add admins.

            is_admin (`bool`, optional):
                Whether the user will be an admin in the chat.
                This will only work in small group chats.
                Whether the user will be an admin in the chat. This is the
                only permission available in small group chats, and when
                used in megagroups, all non-explicitly set permissions will
                have this value.

                Essentially, only passing ``is_admin=True`` will grant all
                permissions, but you can still disable those you need.

            title (`str`, optional):
                The custom title (also known as "rank") to show for this admin.
                This text will be shown instead of the "admin" badge.
                This will only work in channels and megagroups.

                When left unspecified or empty, the default localized "admin"
                badge will be shown.

        Returns
            The resulting :tl:`Updates` object.

        Example
            .. code-block:: python

                # Allowing `user` to pin messages in `chat`
                await client.edit_admin(chat, user, pin_messages=True)

                # Granting all permissions except for `add_admins`
                await client.edit_admin(chat, user, is_admin=True, add_admins=False)
        """
        entity = await self.get_input_entity(entity)
        user = await self.get_input_entity(user)
        if not isinstance(user, (types.InputPeerUser, types.InputPeerSelf)):
            raise ValueError('You must pass a user entity')

        perm_names = (
            'change_info', 'post_messages', 'edit_messages', 'delete_messages',
            'ban_users', 'invite_users', 'pin_messages', 'add_admins'
        )

        if isinstance(entity, types.InputPeerChannel):
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

        elif isinstance(entity, types.InputPeerChat):
            # If the user passed any permission in a small
            # group chat, they must be a full admin to have it.
            if is_admin is None:
                is_admin = any(locals()[x] for x in perm_names)

            return await self(functions.messages.EditChatAdminRequest(
                entity, user, is_admin=is_admin))

        else:
            raise ValueError('You can only edit permissions in groups and channels')

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
            send_polls: bool = True,
            change_info: bool = True,
            invite_users: bool = True,
            pin_messages: bool = True) -> types.Updates:
        """
        Edits user restrictions in a chat.

        Set an argument to `False` to apply a restriction (i.e. remove
        the permission), or omit them to use the default `True` (i.e.
        don't apply a restriction).

        Raises an error if a wrong combination of rights are given
        (e.g. you don't have enough permissions to revoke one).

        By default, each boolean argument is `True`, meaning that it
        is true that the user has access to the default permission
        and may be able to make use of it.

        If you set an argument to `False`, then a restriction is applied
        regardless of the default permissions.

        It is important to note that `True` does *not* mean grant, only
        "don't restrict", and this is where the default permissions come
        in. A user may have not been revoked the ``pin_messages`` permission
        (it is `True`) but they won't be able to use it if the default
        permissions don't allow it either.

        Arguments
            entity (`entity`):
                The channel or megagroup where the restriction should happen.

            user (`entity`, optional):
                If specified, the permission will be changed for the specific user.
                If left as `None`, the default chat permissions will be updated.

            until_date (`DateLike`, optional):
                When the user will be unbanned.

                If the due date or duration is longer than 366 days or shorter than
                30 seconds, the ban will be forever. Defaults to ``0`` (ban forever).

            view_messages (`bool`, optional):
                Whether the user is able to view messages or not.
                Forbidding someone from viewing messages equals to banning them.
                This will only work if ``user`` is set.

            send_messages (`bool`, optional):
                Whether the user is able to send messages or not.

            send_media (`bool`, optional):
                Whether the user is able to send media or not.

            send_stickers (`bool`, optional):
                Whether the user is able to send stickers or not.

            send_gifs (`bool`, optional):
                Whether the user is able to send animated gifs or not.

            send_games (`bool`, optional):
                Whether the user is able to send games or not.

            send_inline (`bool`, optional):
                Whether the user is able to use inline bots or not.

            send_polls (`bool`, optional):
                Whether the user is able to send polls or not.

            change_info (`bool`, optional):
                Whether the user is able to change info or not.

            invite_users (`bool`, optional):
                Whether the user is able to invite other users or not.

            pin_messages (`bool`, optional):
                Whether the user is able to pin messages or not.

        Returns
            The resulting :tl:`Updates` object.

        Example
            .. code-block:: python

                from datetime import timedelta

                # Banning `user` from `chat` for 1 minute
                await client.edit_permissions(chat, user, timedelta(minutes=1),
                                              view_messages=False)

                # Banning `user` from `chat` forever
                await client.edit_permissions(chat, user, view_messages=False)

                # Kicking someone (ban + un-ban)
                await client.edit_permissions(chat, user, view_messages=False)
                await client.edit_permissions(chat, user)
        """
        entity = await self.get_input_entity(entity)
        if not isinstance(entity, types.InputPeerChannel):
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
        if isinstance(user, types.InputPeerSelf):
            raise ValueError('You cannot restrict yourself')

        if not isinstance(user, types.InputPeerUser):
            raise ValueError('You must pass a user entity')

        return await self(functions.channels.EditBannedRequest(
            channel=entity,
            user_id=user,
            banned_rights=rights
        ))

    async def kick_participant(
            self: 'TelegramClient',
            entity: 'hints.EntityLike',
            user: 'typing.Optional[hints.EntityLike]'
    ):
        """
        Kicks a user from a chat.

        Kicking yourself (``'me'``) will result in leaving the chat.

        .. note::

            Attempting to kick someone who was banned will remove their
            restrictions (and thus unbanning them), since kicking is just
            ban + unban.

        Arguments
            entity (`entity`):
                The channel or chat where the user should be kicked from.

            user (`entity`, optional):
                The user to kick.

        Example
            .. code-block:: python

                # Kick some user from some chat
                await client.kick_participant(chat, user)

                # Leaving chat
                await client.kick_participant(chat, 'me')
        """
        entity = await self.get_input_entity(entity)
        user = await self.get_input_entity(user)
        if not isinstance(user, (types.InputPeerUser, types.InputPeerSelf)):
            raise ValueError('You must pass a user entity')

        if isinstance(entity, types.InputPeerChat):
            await self(functions.messages.DeleteChatUserRequest(entity.chat_id, user))
        elif isinstance(entity, types.InputPeerChannel):
            if isinstance(user, types.InputPeerSelf):
                await self(functions.channels.LeaveChannelRequest(entity))
            else:
                await self(functions.channels.EditBannedRequest(
                    channel=entity,
                    user_id=user,
                    banned_rights=types.ChatBannedRights(until_date=None, view_messages=True)
                ))
                await asyncio.sleep(0.5)
                await self(functions.channels.EditBannedRequest(
                    channel=entity,
                    user_id=user,
                    banned_rights=types.ChatBannedRights(until_date=None)
                ))
        else:
            raise ValueError('You must pass either a channel or a chat')

    # endregion
