from async_generator import async_generator, yield_

from .users import UserMethods
from .. import utils, helpers
from ..tl import types, functions


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

    # endregion
