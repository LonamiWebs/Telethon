import itertools
import sys

from async_generator import async_generator, yield_

from .users import UserMethods
from .. import utils, helpers
from ..tl import types, functions, custom


class ChatMethods(UserMethods):

    # region Public methods

    @async_generator
    async def iter_participants(
            self, entity, limit=None, *, search='',
            filter=None, aggressive=False, _total=None):
        """
        Iterator over the participants belonging to the specified chat.

        Args:
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

            _total (`list`, optional):
                A single-item list to pass the total parameter by reference.

        Yields:
            The :tl:`User` objects returned by :tl:`GetParticipantsRequest`
            with an additional ``.participant`` attribute which is the
            matched :tl:`ChannelParticipant` type for channels/megagroups
            or :tl:`ChatParticipants` for normal chats.
        """
        if isinstance(filter, type):
            if filter in (types.ChannelParticipantsBanned,
                          types.ChannelParticipantsKicked,
                          types.ChannelParticipantsSearch):
                # These require a `q` parameter (support types for convenience)
                filter = filter('')
            else:
                filter = filter()

        entity = await self.get_input_entity(entity)
        if search and (filter
                       or not isinstance(entity, types.InputPeerChannel)):
            # We need to 'search' ourselves unless we have a PeerChannel
            search = search.lower()

            def filter_entity(ent):
                return search in utils.get_display_name(ent).lower() or\
                       search in (getattr(ent, 'username', '') or None).lower()
        else:
            def filter_entity(ent):
                return True

        limit = float('inf') if limit is None else int(limit)
        if isinstance(entity, types.InputPeerChannel):
            if _total:
                _total[0] = (await self(
                    functions.channels.GetFullChannelRequest(entity)
                )).full_chat.participants_count

            if limit == 0:
                return

            seen = set()
            if aggressive and not filter:
                requests = [functions.channels.GetParticipantsRequest(
                    channel=entity,
                    filter=types.ChannelParticipantsSearch(x),
                    offset=0,
                    limit=200,
                    hash=0
                ) for x in (search or map(chr, range(ord('a'), ord('z') + 1)))]
            else:
                requests = [functions.channels.GetParticipantsRequest(
                    channel=entity,
                    filter=filter or types.ChannelParticipantsSearch(search),
                    offset=0,
                    limit=200,
                    hash=0
                )]

            while requests:
                # Only care about the limit for the first request
                # (small amount of people, won't be aggressive).
                #
                # Most people won't care about getting exactly 12,345
                # members so it doesn't really matter not to be 100%
                # precise with being out of the offset/limit here.
                requests[0].limit = min(limit - requests[0].offset, 200)
                if requests[0].offset > limit:
                    break

                results = await self(requests)
                for i in reversed(range(len(requests))):
                    participants = results[i]
                    if not participants.users:
                        requests.pop(i)
                    else:
                        requests[i].offset += len(participants.participants)
                        users = {user.id: user for user in participants.users}
                        for participant in participants.participants:
                            user = users[participant.user_id]
                            if not filter_entity(user) or user.id in seen:
                                continue

                            seen.add(participant.user_id)
                            user = users[participant.user_id]
                            user.participant = participant
                            await yield_(user)
                            if len(seen) >= limit:
                                return

        elif isinstance(entity, types.InputPeerChat):
            full = await self(
                functions.messages.GetFullChatRequest(entity.chat_id))
            if not isinstance(
                    full.full_chat.participants, types.ChatParticipants):
                # ChatParticipantsForbidden won't have ``.participants``
                if _total:
                    _total[0] = 0
                return

            if _total:
                _total[0] = len(full.full_chat.participants.participants)

            have = 0
            users = {user.id: user for user in full.users}
            for participant in full.full_chat.participants.participants:
                user = users[participant.user_id]
                if not filter_entity(user):
                    continue
                have += 1
                if have > limit:
                    break
                else:
                    user = users[participant.user_id]
                    user.participant = participant
                    await yield_(user)
        else:
            if _total:
                _total[0] = 1
            if limit != 0:
                user = await self.get_entity(entity)
                if filter_entity(user):
                    user.participant = None
                    await yield_(user)

    async def get_participants(self, *args, **kwargs):
        """
        Same as `iter_participants`, but returns a
        `TotalList <telethon.helpers.TotalList>` instead.
        """
        total = [0]
        kwargs['_total'] = total
        participants = helpers.TotalList()
        async for x in self.iter_participants(*args, **kwargs):
            participants.append(x)
        participants.total = total[0]
        return participants

    @async_generator
    async def iter_admin_log(
            self, entity, limit=None, *, max_id=0, min_id=0, search=None,
            admins=None, join=None, leave=None, invite=None, restrict=None,
            unrestrict=None, ban=None, unban=None, promote=None, demote=None,
            info=None, settings=None, pinned=None, edit=None, delete=None):
        """
        Iterator over the admin log for the specified channel.

        Note that you must be an administrator of it to use this method.

        If none of the filters are present (i.e. they all are ``None``),
        *all* event types will be returned. If at least one of them is
        ``True``, only those that are true will be returned.

        Args:
            entity (`entity`):
                The channel entity from which to get its admin log.

            limit (`int` | `None`, optional):
                Number of events to be retrieved.

                The limit may also be ``None``, which would eventually return
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
                If ``True``, events for when a user joined will be returned.

            leave (`bool`):
                If ``True``, events for when a user leaves will be returned.

            invite (`bool`):
                If ``True``, events for when a user joins through an invite
                link will be returned.

            restrict (`bool`):
                If ``True``, events with partial restrictions will be
                returned. This is what the API calls "ban".

            unrestrict (`bool`):
                If ``True``, events removing restrictions will be returned.
                This is what the API calls "unban".

            ban (`bool`):
                If ``True``, events applying or removing all restrictions will
                be returned. This is what the API calls "kick" (restricting
                all permissions removed is a ban, which kicks the user).

            unban (`bool`):
                If ``True``, events removing all restrictions will be
                returned. This is what the API calls "unkick".

            promote (`bool`):
                If ``True``, events with admin promotions will be returned.

            demote (`bool`):
                If ``True``, events with admin demotions will be returned.

            info (`bool`):
                If ``True``, events changing the group info will be returned.

            settings (`bool`):
                If ``True``, events changing the group settings will be
                returned.

            pinned (`bool`):
                If ``True``, events of new pinned messages will be returned.

            edit (`bool`):
                If ``True``, events of message edits will be returned.

            delete (`bool`):
                If ``True``, events of message deletions will be returned.

        Yields:
            Instances of `telethon.tl.custom.adminlogevent.AdminLogEvent`.
        """
        if limit is None:
            limit = sys.maxsize
        elif limit <= 0:
            return

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

        entity = await self.get_input_entity(entity)

        admin_list = []
        if admins:
            if not utils.is_list_like(admins):
                admins = (admins,)

            for admin in admins:
                admin_list.append(await self.get_input_entity(admin))

        request = functions.channels.GetAdminLogRequest(
            entity, q=search or '', min_id=min_id, max_id=max_id,
            limit=0, events_filter=events_filter, admins=admin_list or None
        )
        while limit > 0:
            request.limit = min(limit, 100)
            result = await self(request)
            limit -= len(result.events)
            entities = {utils.get_peer_id(x): x
                        for x in itertools.chain(result.users, result.chats)}

            request.max_id = min((e.id for e in result.events), default=0)
            for ev in result.events:
                if isinstance(ev.action,
                              types.ChannelAdminLogEventActionEditMessage):
                    ev.action.prev_message._finish_init(self, entities, entity)
                    ev.action.new_message._finish_init(self, entities, entity)

                elif isinstance(ev.action,
                                types.ChannelAdminLogEventActionDeleteMessage):
                    ev.action.message._finish_init(self, entities, entity)

                await yield_(custom.AdminLogEvent(ev, entities))

            if len(result.events) < request.limit:
                break

    async def get_admin_log(self, *args, **kwargs):
        """
        Same as `iter_admin_log`, but returns a ``list`` instead.
        """
        admin_log = []
        async for x in self.iter_admin_log(*args, **kwargs):
            admin_log.append(x)
        return admin_log

    # endregion
