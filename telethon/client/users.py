import asyncio
import itertools

from .telegrambaseclient import TelegramBaseClient
from .. import errors, utils
from ..tl import TLObject, TLRequest, types, functions


_NOT_A_REQUEST = TypeError('You can only invoke requests, not types!')


class UserMethods(TelegramBaseClient):
    async def __call__(self, request, retries=5, ordered=False):
        for r in (request if utils.is_list_like(request) else (request,)):
            if not isinstance(r, TLRequest):
                raise _NOT_A_REQUEST
            await r.resolve(self, utils)

        for _ in range(retries):
            try:
                future = self._sender.send(request, ordered=ordered)
                if isinstance(future, list):
                    results = []
                    for f in future:
                        results.append(await f)
                    return results
                else:
                    return await future
            except (errors.ServerError, errors.RpcCallFailError):
                pass
            except (errors.FloodWaitError, errors.FloodTestPhoneWaitError) as e:
                if e.seconds <= self.session.flood_sleep_threshold:
                    await asyncio.sleep(e.seconds, loop=self._loop)
                else:
                    raise
            except (errors.PhoneMigrateError, errors.NetworkMigrateError,
                    errors.UserMigrateError) as e:
                await self._switch_dc(e.new_dc)

        raise ValueError('Number of retries reached 0')

    # region Public methods

    async def get_me(self, input_peer=False):
        """
        Gets "me" (the self user) which is currently authenticated,
        or None if the request fails (hence, not authenticated).

        Args:
            input_peer (`bool`, optional):
                Whether to return the :tl:`InputPeerUser` version or the normal
                :tl:`User`. This can be useful if you just need to know the ID
                of yourself.

        Returns:
            Your own :tl:`User`.
        """
        if input_peer and self._self_input_peer:
            return self._self_input_peer

        try:
            me = (await self(
                functions.users.GetUsersRequest([types.InputUserSelf()])))[0]

            if not self._self_input_peer:
                self._self_input_peer = utils.get_input_peer(
                    me, allow_self=False
                )

            return self._self_input_peer if input_peer else me
        except errors.UnauthorizedError:
            return None

    async def get_entity(self, entity):
        """
        Turns the given entity into a valid Telegram user or chat.

        entity (`str` | `int` | :tl:`Peer` | :tl:`InputPeer`):
            The entity (or iterable of entities) to be transformed.
            If it's a string which can be converted to an integer or starts
            with '+' it will be resolved as if it were a phone number.

            If it doesn't start with '+' or starts with a '@' it will be
            be resolved from the username. If no exact match is returned,
            an error will be raised.

            If the entity is an integer or a Peer, its information will be
            returned through a call to self.get_input_peer(entity).

            If the entity is neither, and it's not a TLObject, an
            error will be raised.

        Returns:
            :tl:`User`, :tl:`Chat` or :tl:`Channel` corresponding to the
            input entity. A list will be returned if more than one was given.
        """
        single = not utils.is_list_like(entity)
        if single:
            entity = (entity,)

        # Group input entities by string (resolve username),
        # input users (get users), input chat (get chats) and
        # input channels (get channels) to get the most entities
        # in the less amount of calls possible.
        inputs = [
            x if isinstance(x, str) else await self.get_input_entity(x)
            for x in entity
        ]
        users = [x for x in inputs
                 if isinstance(x, (types.InputPeerUser, types.InputPeerSelf))]
        chats = [x.chat_id for x in inputs
                 if isinstance(x, types.InputPeerChat)]
        channels = [x for x in inputs
                    if isinstance(x, types.InputPeerChannel)]
        if users:
            # GetUsersRequest has a limit of 200 per call
            tmp = []
            while users:
                curr, users = users[:200], users[200:]
                tmp.extend(await self(functions.users.GetUsersRequest(curr)))
            users = tmp
        if chats:  # TODO Handle chats slice?
            chats = (await self(
                functions.messages.GetChatsRequest(chats))).chats
        if channels:
            channels = (await self(
                functions.channels.GetChannelsRequest(channels))).chats

        # Merge users, chats and channels into a single dictionary
        id_entity = {
            utils.get_peer_id(x): x
            for x in itertools.chain(users, chats, channels)
        }

        # We could check saved usernames and put them into the users,
        # chats and channels list from before. While this would reduce
        # the amount of ResolveUsername calls, it would fail to catch
        # username changes.
        result = [
            await self._get_entity_from_string(x) if isinstance(x, str)
            else (
                id_entity[utils.get_peer_id(x)]
                if not isinstance(x, types.InputPeerSelf)
                else next(u for u in id_entity.values()
                          if isinstance(u, types.User) and u.is_self)
            )
            for x in inputs
        ]
        return result[0] if single else result

    async def get_input_entity(self, peer):
        """
        Turns the given peer into its input entity version. Most requests
        use this kind of InputUser, InputChat and so on, so this is the
        most suitable call to make for those cases.

        entity (`str` | `int` | :tl:`Peer` | :tl:`InputPeer`):
            The integer ID of an user or otherwise either of a
            :tl:`PeerUser`, :tl:`PeerChat` or :tl:`PeerChannel`, for
            which to get its ``Input*`` version.

            If this ``Peer`` hasn't been seen before by the library, the top
            dialogs will be loaded and their entities saved to the session
            file (unless this feature was disabled explicitly).

            If in the end the access hash required for the peer was not found,
            a ValueError will be raised.

        Returns:
            :tl:`InputPeerUser`, :tl:`InputPeerChat` or :tl:`InputPeerChannel`
            or :tl:`InputPeerSelf` if the parameter is ``'me'`` or ``'self'``.

            If you need to get the ID of yourself, you should use
            `get_me` with ``input_peer=True``) instead.
        """
        if peer in ('me', 'self'):
            return types.InputPeerSelf()

        try:
            # First try to get the entity from cache, otherwise figure it out
            return self.session.get_input_entity(peer)
        except ValueError:
            pass

        if isinstance(peer, str):
            return utils.get_input_peer(
                await self._get_entity_from_string(peer))

        if not isinstance(peer, int) and (not isinstance(peer, TLObject)
                                          or peer.SUBCLASS_OF_ID != 0x2d45687):
            # Try casting the object into an input peer. Might TypeError.
            # Don't do it if a not-found ID was given (instead ValueError).
            # Also ignore Peer (0x2d45687 == crc32(b'Peer'))'s, lacking hash.
            return utils.get_input_peer(peer)

        raise ValueError(
            'Could not find the input entity for "{}". Please read https://'
            'telethon.readthedocs.io/en/latest/extra/basic/entities.html to'
            ' find out more details.'
            .format(peer)
        )

    # endregion

    # region Private methods

    async def _get_entity_from_string(self, string):
        """
        Gets a full entity from the given string, which may be a phone or
        an username, and processes all the found entities on the session.
        The string may also be a user link, or a channel/chat invite link.

        This method has the side effect of adding the found users to the
        session database, so it can be queried later without API calls,
        if this option is enabled on the session.

        Returns the found entity, or raises TypeError if not found.
        """
        phone = utils.parse_phone(string)
        if phone:
            for user in (await self(
                    functions.contacts.GetContactsRequest(0))).users:
                if user.phone == phone:
                    return user
        else:
            username, is_join_chat = utils.parse_username(string)
            if is_join_chat:
                invite = await self(
                    functions.messages.CheckChatInviteRequest(username))

                if isinstance(invite, types.ChatInvite):
                    raise ValueError(
                        'Cannot get entity from a channel (or group) '
                        'that you are not part of. Join the group and retry'
                    )
                elif isinstance(invite, types.ChatInviteAlready):
                    return invite.chat
            elif username:
                if username in ('me', 'self'):
                    return await self.get_me()

                try:
                    result = await self(
                        functions.contacts.ResolveUsernameRequest(username))
                except errors.UsernameNotOccupiedError as e:
                    raise ValueError('No user has "{}" as username'
                                     .format(username)) from e

                for entity in itertools.chain(result.users, result.chats):
                    if getattr(entity, 'username', None) or '' \
                            .lower() == username:
                        return entity
            try:
                # Nobody with this username, maybe it's an exact name/title
                return await self.get_entity(
                    self.session.get_input_entity(string))
            except ValueError:
                pass

        raise ValueError(
            'Cannot find any entity corresponding to "{}"'.format(string)
        )

    # endregion
