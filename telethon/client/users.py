import asyncio
import itertools
import time
import typing

from .telegrambaseclient import TelegramBaseClient
from .. import errors, utils, hints
from ..errors import MultiError, RPCError
from ..helpers import retry_range
from ..tl import TLRequest, types, functions

_NOT_A_REQUEST = lambda: TypeError('You can only invoke requests, not types!')

if typing.TYPE_CHECKING:
    from .telegramclient import TelegramClient


class UserMethods(TelegramBaseClient):
    async def __call__(self: 'TelegramClient', request, ordered=False):
        requests = (request if utils.is_list_like(request) else (request,))
        for r in requests:
            if not isinstance(r, TLRequest):
                raise _NOT_A_REQUEST()
            await r.resolve(self, utils)

            # Avoid making the request if it's already in a flood wait
            if r.CONSTRUCTOR_ID in self._flood_waited_requests:
                due = self._flood_waited_requests[r.CONSTRUCTOR_ID]
                diff = round(due - time.time())
                if diff <= 3:  # Flood waits below 3 seconds are "ignored"
                    self._flood_waited_requests.pop(r.CONSTRUCTOR_ID, None)
                elif diff <= self.flood_sleep_threshold:
                    self._log[__name__].info(
                        'Sleeping early for %ds on flood wait', diff)
                    await asyncio.sleep(diff, loop=self._loop)
                    self._flood_waited_requests.pop(r.CONSTRUCTOR_ID, None)
                else:
                    raise errors.FloodWaitError(request=r, capture=diff)

        request_index = 0
        self._last_request = time.time()
        for attempt in retry_range(self._request_retries):
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
                        self._entity_cache.add(result)
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
                    self._entity_cache.add(result)
                    return result
            except (errors.ServerError, errors.RpcCallFailError,
                    errors.RpcMcgetFailError) as e:
                self._log[__name__].warning(
                    'Telegram is having internal issues %s: %s',
                    e.__class__.__name__, e)

                await asyncio.sleep(2)
            except (errors.FloodWaitError, errors.FloodTestPhoneWaitError) as e:
                if utils.is_list_like(request):
                    request = request[request_index]

                self._flood_waited_requests\
                    [request.CONSTRUCTOR_ID] = time.time() + e.seconds

                if e.seconds <= self.flood_sleep_threshold:
                    self._log[__name__].info('Sleeping for %ds on flood wait',
                                             e.seconds)
                    await asyncio.sleep(e.seconds, loop=self._loop)
                else:
                    raise
            except (errors.PhoneMigrateError, errors.NetworkMigrateError,
                    errors.UserMigrateError) as e:
                self._log[__name__].info('Phone migrated to %d', e.new_dc)
                should_raise = isinstance(e, (
                    errors.PhoneMigrateError, errors.NetworkMigrateError
                ))
                if should_raise and await self.is_user_authorized():
                    raise
                await self._switch_dc(e.new_dc)

        raise ValueError('Request was unsuccessful {} time(s)'
                         .format(attempt))

    # region Public methods

    async def get_me(self: 'TelegramClient', input_peer: bool = False) \
            -> 'typing.Union[types.User, types.InputPeerUser]':
        """
        Gets "me", the current :tl:`User` who is logged in.

        If the user has not logged in yet, this method returns ``None``.

        Arguments
            input_peer (`bool`, optional):
                Whether to return the :tl:`InputPeerUser` version or the normal
                :tl:`User`. This can be useful if you just need to know the ID
                of yourself.

        Returns
            Your own :tl:`User`.

        Example
            .. code-block:: python

                print(client.get_me().username)
        """
        if input_peer and self._self_input_peer:
            return self._self_input_peer

        try:
            me = (await self(
                functions.users.GetUsersRequest([types.InputUserSelf()])))[0]

            self._bot = me.bot
            if not self._self_input_peer:
                self._self_input_peer = utils.get_input_peer(
                    me, allow_self=False
                )

            return self._self_input_peer if input_peer else me
        except errors.UnauthorizedError:
            return None

    async def is_bot(self: 'TelegramClient') -> bool:
        """
        Return ``True`` if the signed-in user is a bot, ``False`` otherwise.

        Example
            .. code-block:: python

                if client.is_bot():
                    print('Beep')
                else:
                    print('Hello')
        """
        if self._bot is None:
            self._bot = (await self.get_me()).bot

        return self._bot

    async def is_user_authorized(self: 'TelegramClient') -> bool:
        """
        Returns ``True`` if the user is authorized (i.e. has logged in).

        Example
            .. code-block:: python

                if not client.is_user_authorized():
                    client.send_code_request(phone)
                    code = input('enter code: ')
                    client.sign_in(phone, code)
        """
        if self._authorized is None:
            try:
                # Any request that requires authorization will work
                await self(functions.updates.GetStateRequest())
                self._authorized = True
            except errors.RPCError:
                self._authorized = False

        return self._authorized

    async def get_entity(
            self: 'TelegramClient',
            entity: 'hints.EntitiesLike') -> 'hints.Entity':
        """
        Turns the given entity into a valid Telegram :tl:`User`, :tl:`Chat`
        or :tl:`Channel`. You can also pass a list or iterable of entities,
        and they will be efficiently fetched from the network.

        Arguments
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

                Using phone numbers (from people in your contact list), exact
                names, integer IDs or :tl:`Peer` rely on a `get_input_entity`
                first, which in turn needs the entity to be in cache, unless
                a :tl:`InputPeer` was passed.

                Unsupported types will raise ``TypeError``.

                If the entity can't be found, ``ValueError`` will be raised.

        Returns
            :tl:`User`, :tl:`Chat` or :tl:`Channel` corresponding to the
            input entity. A list will be returned if more than one was given.

        Example
            .. code-block:: python

                from telethon import utils

                me = client.get_entity('me')
                print(utils.get_display_name(me))

                chat = client.get_input_entity('username')
                for message in client.iter_messages(chat):
                    ...

                # Note that you could have used the username directly, but it's
                # good to use get_input_entity if you will reuse it a lot.
                for message in client.iter_messages('username'):
                    ...

                # Note that for this to work the phone number must be in your contacts
                some_id = client.get_peer_id('+34123456789')
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

    async def get_input_entity(
            self: 'TelegramClient',
            peer: 'hints.EntityLike') -> 'types.TypeInputPeer':
        """
        Turns the given entity into its input entity version.

        Most requests use this kind of :tl:`InputPeer`, so this is the most
        suitable call to make for those cases. **Generally you should let the
        library do its job** and don't worry about getting the input entity
        first, but if you're going to use an entity often, consider making the
        call:

        Arguments
            entity (`str` | `int` | :tl:`Peer` | :tl:`InputPeer`):
                If a username or invite link is given, **the library will
                use the cache**. This means that it's possible to be using
                a username that *changed* or an old invite link (this only
                happens if an invite link for a small group chat is used
                after it was upgraded to a mega-group).

                If the username or ID from the invite link is not found in
                the cache, it will be fetched. The same rules apply to phone
                numbers (``'+34 123456789'``) from people in your contact list.

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

        Returns
            :tl:`InputPeerUser`, :tl:`InputPeerChat` or :tl:`InputPeerChannel`
            or :tl:`InputPeerSelf` if the parameter is ``'me'`` or ``'self'``.

            If you need to get the ID of yourself, you should use
            `get_me` with ``input_peer=True``) instead.

        Example
            .. code-block:: python

                # If you're going to use "username" often in your code
                # (make a lot of calls), consider getting its input entity
                # once, and then using the "user" everywhere instead.
                user = client.get_input_entity('username')

                # The same applies to IDs, chats or channels.
                chat = client.get_input_entity(-123456789)
        """
        # Short-circuit if the input parameter directly maps to an InputPeer
        try:
            return utils.get_input_peer(peer)
        except TypeError:
            pass

        # Next in priority is having a peer (or its ID) cached in-memory
        try:
            # 0x2d45687 == crc32(b'Peer')
            if isinstance(peer, int) or peer.SUBCLASS_OF_ID == 0x2d45687:
                return self._entity_cache[peer]
        except (AttributeError, KeyError):
            pass

        # Then come known strings that take precedence
        if peer in ('me', 'self'):
            return types.InputPeerSelf()

        # No InputPeer, cached peer, or known string. Fetch from disk cache
        try:
            return self.session.get_input_entity(peer)
        except ValueError:
            pass

        # Only network left to try
        if isinstance(peer, str):
            return utils.get_input_peer(
                await self._get_entity_from_string(peer))

        # If we're a bot and the user has messaged us privately users.getUsers
        # will work with access_hash = 0. Similar for channels.getChannels.
        # If we're not a bot but the user is in our contacts, it seems to work
        # regardless. These are the only two special-cased requests.
        peer = utils.get_peer(peer)
        if isinstance(peer, types.PeerUser):
            users = await self(functions.users.GetUsersRequest([
                types.InputUser(peer.user_id, access_hash=0)]))
            if users and not isinstance(users[0], types.UserEmpty):
                # If the user passed a valid ID they expect to work for
                # channels but would be valid for users, we get UserEmpty.
                # Avoid returning the invalid empty input peer for that.
                #
                # We *could* try to guess if it's a channel first, and if
                # it's not, work as a chat and try to validate it through
                # another request, but that becomes too much work.
                return utils.get_input_peer(users[0])
        elif isinstance(peer, types.PeerChat):
            return types.InputPeerChat(peer.chat_id)
        elif isinstance(peer, types.PeerChannel):
            try:
                channels = await self(functions.channels.GetChannelsRequest([
                    types.InputChannel(peer.channel_id, access_hash=0)]))
                return utils.get_input_peer(channels.chats[0])
            except errors.ChannelInvalidError:
                pass

        raise ValueError(
            'Could not find the input entity for {!r}. Please read https://'
            'docs.telethon.dev/en/latest/concepts/entities.html to'
            ' find out more details.'
            .format(peer)
        )

    async def get_peer_id(
            self: 'TelegramClient',
            peer: 'hints.EntityLike',
            add_mark: bool = True) -> int:
        """
        Gets the ID for the given entity.

        This method needs to be ``async`` because `peer` supports usernames,
        invite-links, phone numbers (from people in your contact list), etc.

        If ``add_mark is False``, then a positive ID will be returned
        instead. By default, bot-API style IDs (signed) are returned.

        Example
            .. code-block:: python

                print(client.get_peer_id('me'))
        """
        if isinstance(peer, int):
            return utils.get_peer_id(peer, add_mark=add_mark)

        try:
            if peer.SUBCLASS_OF_ID not in (0x2d45687, 0xc91c90b6):
                # 0x2d45687, 0xc91c90b6 == crc32(b'Peer') and b'InputPeer'
                peer = await self.get_input_entity(peer)
        except AttributeError:
            peer = await self.get_input_entity(peer)

        if isinstance(peer, types.InputPeerSelf):
            peer = await self.get_me(input_peer=True)

        return utils.get_peer_id(peer, add_mark=add_mark)

    # endregion

    # region Private methods

    async def _get_entity_from_string(self: 'TelegramClient', string):
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
            try:
                for user in (await self(
                        functions.contacts.GetContactsRequest(0))).users:
                    if user.phone == phone:
                        return user
            except errors.BotMethodInvalidError:
                raise ValueError('Cannot get entity by phone number as a '
                                 'bot (try using integer IDs, not strings)')
        elif string.lower() in ('me', 'self'):
            return await self.get_me()
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

    async def _get_input_dialog(self: 'TelegramClient', dialog):
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

    async def _get_input_notify(self: 'TelegramClient', notify):
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
