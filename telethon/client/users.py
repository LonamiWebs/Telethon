import asyncio
import itertools
import logging
import time

from .telegrambaseclient import TelegramBaseClient
from .. import errors, utils
from ..tl import TLObject, TLRequest, types, functions
from ..errors import MultiError, RPCError

__log__ = logging.getLogger(__name__)
_NOT_A_REQUEST = TypeError('You can only invoke requests, not types!')


class UserMethods(TelegramBaseClient):
    async def __call__(self, request, ordered=False):
        requests = (request if utils.is_list_like(request) else (request,))
        for r in requests:
            if not isinstance(r, TLRequest):
                raise _NOT_A_REQUEST
            await r.resolve(self, utils)

            # Avoid making the request if it's already in a flood wait
            if r.CONSTRUCTOR_ID in self._flood_waited_requests:
                due = self._flood_waited_requests[r.CONSTRUCTOR_ID]
                diff = round(due - time.time())
                if diff <= 3:  # Flood waits below 3 seconds are "ignored"
                    self._flood_waited_requests.pop(r.CONSTRUCTOR_ID, None)
                elif diff <= self.flood_sleep_threshold:
                    __log__.info('Sleeping early for %ds on flood wait', diff)
                    await asyncio.sleep(diff, loop=self._loop)
                    self._flood_waited_requests.pop(r.CONSTRUCTOR_ID, None)
                else:
                    raise errors.FloodWaitError(capture=diff)

        request_index = 0
        self._last_request = time.time()
        for _ in range(self._request_retries):
            try:
                future = self._sender.send(request, ordered=ordered)
                if isinstance(future, list):
                    results = []
                    exceptions = []
                    for f in future:
                        try:
                            result = await f
                        except RPCError as e:
                            exceptions.append(e)
                            results.append(None)
                            continue
                        self.session.process_entities(result)
                        exceptions.append(None)
                        results.append(result)
                        request_index += 1
                    if any(x is not None for x in exceptions):
                        raise MultiError(exceptions, results, requests)
                    else:
                        return results
                else:
                    result = await future
                    self.session.process_entities(result)
                    return result
            except (errors.ServerError, errors.RpcCallFailError) as e:
                __log__.warning('Telegram is having internal issues %s: %s',
                                e.__class__.__name__, e)
            except (errors.FloodWaitError, errors.FloodTestPhoneWaitError) as e:
                if utils.is_list_like(request):
                    request = request[request_index]

                self._flood_waited_requests\
                    [request.CONSTRUCTOR_ID] = time.time() + e.seconds

                if e.seconds <= self.flood_sleep_threshold:
                    __log__.info('Sleeping for %ds on flood wait', e.seconds)
                    await asyncio.sleep(e.seconds, loop=self._loop)
                else:
                    raise
            except (errors.PhoneMigrateError, errors.NetworkMigrateError,
                    errors.UserMigrateError) as e:
                __log__.info('Phone migrated to %d', e.new_dc)
                should_raise = isinstance(e, (
                    errors.PhoneMigrateError,  errors.NetworkMigrateError
                ))
                if should_raise and await self.is_user_authorized():
                    raise
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

    async def is_user_authorized(self):
        """
        Returns ``True`` if the user is authorized.
        """
        if self._self_input_peer is not None or self._state.pts != -1:
            return True

        try:
            self._state = await self(functions.updates.GetStateRequest())
            return True
        except errors.RPCError:
            return False

    async def get_entity(self, entity):
        """
        Turns the given entity into a valid Telegram :tl:`User`, :tl:`Chat`
        or :tl:`Channel`. You can also pass a list or iterable of entities,
        and they will be efficiently fetched from the network.

        entity (`str` | `int` | :tl:`Peer` | :tl:`InputPeer`):
            If a username is given, **the username will be resolved** making
            an API call every time. Resolving usernames is an expensive
            operation and will start hitting flood waits around 50 usernames
            in a short period of time.

            If you want to get the entity for a *cached* username, you should
            first `get_input_entity(username) <get_input_entity>` which will
            use the cache), and then use `get_entity` with the result of the
            previous call.

            Similar limits apply to invite links, and you should use their
            ID instead.

            Using phone numbers, exact names, integer IDs or :tl:`Peer`
            rely on a `get_input_entity` first, which in turn needs the
            entity to be in cache, unless a :tl:`InputPeer` was passed.

            Unsupported types will raise ``TypeError``.

            If the entity can't be found, ``ValueError`` will be raised.

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
        inputs = []
        for x in entity:
            if isinstance(x, str):
                inputs.append(x)
            else:
                inputs.append(await self.get_input_entity(x))

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
        result = []
        for x in inputs:
            if isinstance(x, str):
                result.append(await self._get_entity_from_string(x))
            elif not isinstance(x, types.InputPeerSelf):
                result.append(id_entity[utils.get_peer_id(x)])
            else:
                result.append(next(
                    u for u in id_entity.values()
                    if isinstance(u, types.User) and u.is_self
                ))

        return result[0] if single else result

    async def get_input_entity(self, peer):
        """
        Turns the given peer into its input entity version. Most requests
        use this kind of :tl:`InputPeer`, so this is the most suitable call
        to make for those cases. **Generally you should let the library do
        its job** and don't worry about getting the input entity first, but
        if you're going to use an entity often, consider making the call:

        >>> import asyncio
        >>> rc = asyncio.get_event_loop().run_until_complete
        >>>
        >>> from telethon import TelegramClient
        >>> client = TelegramClient(...)
        >>> # If you're going to use "username" often in your code
        >>> # (make a lot of calls), consider getting its input entity
        >>> # once, and then using the "user" everywhere instead.
        >>> user = rc(client.get_input_entity('username'))
        >>> # The same applies to IDs, chats or channels.
        >>> chat = rc(client.get_input_entity(-123456789))

        entity (`str` | `int` | :tl:`Peer` | :tl:`InputPeer`):
            If a username or invite link is given, **the library will
            use the cache**. This means that it's possible to be using
            a username that *changed* or an old invite link (this only
            happens if an invite link for a small group chat is used
            after it was upgraded to a mega-group).

            If the username or ID from the invite link is not found in
            the cache, it will be fetched. The same rules apply to phone
            numbers (``'+34 123456789'``).

            If an exact name is given, it must be in the cache too. This
            is not reliable as different people can share the same name
            and which entity is returned is arbitrary, and should be used
            only for quick tests.

            If a positive integer ID is given, the entity will be searched
            in cached users, chats or channels, without making any call.

            If a negative integer ID is given, the entity will be searched
            exactly as either a chat (prefixed with ``-``) or as a channel
            (prefixed with ``-100``).

            If a :tl:`Peer` is given, it will be searched exactly in the
            cache as either a user, chat or channel.

            If the given object can be turned into an input entity directly,
            said operation will be done.

            Unsupported types will raise ``TypeError``.

            If the entity can't be found, ``ValueError`` will be raised.

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

    async def get_peer_id(self, peer, add_mark=True):
        """
        Gets the ID for the given peer, which may be anything entity-like.

        This method needs to be ``async`` because `peer` supports usernames,
        invite-links, phone numbers, etc.

        If ``add_mark is False``, then a positive ID will be returned
        instead. By default, bot-API style IDs (signed) are returned.
        """
        if isinstance(peer, int):
            return utils.get_peer_id(peer, add_mark=add_mark)

        try:
            if peer.SUBCLASS_OF_ID in (0x2d45687, 0xc91c90b6):
                # 0x2d45687, 0xc91c90b6 == crc32(b'Peer') and b'InputPeer'
                return utils.get_peer_id(peer)
        except AttributeError:
            pass

        peer = await self.get_input_entity(peer)
        if isinstance(peer, types.InputPeerSelf):
            peer = await self.get_me(input_peer=True)

        return utils.get_peer_id(peer, add_mark=add_mark)

    # endregion

    # region Private methods

    async def _get_entity_from_string(self, string):
        """
        Gets a full entity from the given string, which may be a phone or
        a username, and processes all the found entities on the session.
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

                try:
                    pid = utils.get_peer_id(result.peer, add_mark=False)
                    if isinstance(result.peer, types.PeerUser):
                        return next(x for x in result.users if x.id == pid)
                    else:
                        return next(x for x in result.chats if x.id == pid)
                except StopIteration:
                    pass
            try:
                # Nobody with this username, maybe it's an exact name/title
                return await self.get_entity(
                    self.session.get_input_entity(string))
            except ValueError:
                pass

        raise ValueError(
            'Cannot find any entity corresponding to "{}"'.format(string)
        )

    async def _get_input_dialog(self, dialog):
        """
        Returns a :tl:`InputDialogPeer`. This is a bit tricky because
        it may or not need access to the client to convert what's given
        into an input entity.
        """
        try:
            if dialog.SUBCLASS_OF_ID == 0xa21c9795:  # crc32(b'InputDialogPeer')
                dialog.peer = await self.get_input_entity(dialog.peer)
                return dialog
            elif dialog.SUBCLASS_OF_ID == 0xc91c90b6:  # crc32(b'InputPeer')
                return types.InputDialogPeer(dialog)
        except AttributeError:
            pass

        return types.InputDialogPeer(await self.get_input_entity(dialog))

    async def _get_input_notify(self, notify):
        """
        Returns a :tl:`InputNotifyPeer`. This is a bit tricky because
        it may or not need access to the client to convert what's given
        into an input entity.
        """
        try:
            if notify.SUBCLASS_OF_ID == 0x58981615:
                if isinstance(notify, types.InputNotifyPeer):
                    notify.peer = await self.get_input_entity(notify.peer)
                return notify
        except AttributeError:
            return types.InputNotifyPeer(await self.get_input_entity(notify))

    # endregion
