import asyncio
import datetime
import itertools
import time
import typing

from ..errors._custom import MultiError
from ..errors._rpcbase import RpcError, ServerError, FloodError, InvalidDcError, UnauthorizedError
from .._misc import helpers, utils, hints
from .._sessions.types import Entity, get_peer_canonical_entity_type
from .. import errors, _tl

_NOT_A_REQUEST = lambda: TypeError('You can only invoke requests, not types!')

if typing.TYPE_CHECKING:
    from .telegramclient import TelegramClient


def _fmt_flood(delay, request, *, early=False, td=datetime.timedelta):
    return (
        'Sleeping%s for %ds (%s) on %s flood wait',
        ' early' if early else '',
        delay,
        td(seconds=delay),
        request.__class__.__name__
    )


async def call(self: 'TelegramClient', request, ordered=False, flood_sleep_threshold=None):
    return await _call(self, self._sender, request, ordered=ordered)


async def _call(self: 'TelegramClient', sender, request, ordered=False, flood_sleep_threshold=None):
    if flood_sleep_threshold is None:
        flood_sleep_threshold = self.flood_sleep_threshold
    requests = (request if utils.is_list_like(request) else (request,))
    for r in requests:
        if not isinstance(r, _tl.TLRequest):
            raise _NOT_A_REQUEST()
        await r.resolve(self, utils)

        # Avoid making the request if it's already in a flood wait
        if r.CONSTRUCTOR_ID in self._flood_waited_requests:
            due = self._flood_waited_requests[r.CONSTRUCTOR_ID]
            diff = round(due - time.time())
            if diff <= 3:  # Flood waits below 3 seconds are "ignored"
                self._flood_waited_requests.pop(r.CONSTRUCTOR_ID, None)
            elif diff <= flood_sleep_threshold:
                self._log[__name__].info(*_fmt_flood(diff, r, early=True))
                await asyncio.sleep(diff)
                self._flood_waited_requests.pop(r.CONSTRUCTOR_ID, None)
            else:
                raise errors.FLOOD_WAIT(420, f'FLOOD_WAIT_{diff}', request=r)

        if self._no_updates:
            r = _tl.fn.InvokeWithoutUpdates(r)

    request_index = 0
    last_error = None
    self._last_request = time.time()

    for attempt in helpers.retry_range(self._request_retries):
        try:
            future = sender.send(request, ordered=ordered)
            if isinstance(future, list):
                results = []
                exceptions = []
                for f in future:
                    try:
                        result = await f
                    except RpcError as e:
                        exceptions.append(e)
                        results.append(None)
                        continue
                    entities = self._entity_cache.add(result)
                    if entities:
                        await self.session.insert_entities(entities)
                    exceptions.append(None)
                    results.append(result)
                    request_index += 1
                if any(x is not None for x in exceptions):
                    raise MultiError(exceptions, results, requests)
                else:
                    return results
            else:
                result = await future
                entities = self._entity_cache.add(result)
                if entities:
                    await self.session.insert_entities(entities)
                return result
        except ServerError as e:
            last_error = e
            self._log[__name__].warning(
                'Telegram is having internal issues %s: %s',
                e.__class__.__name__, e)

            await asyncio.sleep(2)
        except FloodError as e:
            last_error = e
            if utils.is_list_like(request):
                request = request[request_index]

            # SLOWMODE_WAIT is chat-specific, not request-specific
            if not isinstance(e, errors.SLOWMODE_WAIT):
                # TODO reconsider use of time.time() - maybe monotonic or server time is better.
                self._flood_waited_requests \
                    [request.CONSTRUCTOR_ID] = time.time() + e.seconds

            # In test servers, FLOOD_WAIT_0 has been observed, and sleeping for
            # such a short amount will cause retries very fast leading to issues.
            seconds = e.seconds or 1

            if seconds <= self.flood_sleep_threshold:
                self._log[__name__].info(*_fmt_flood(seconds, request))
                await asyncio.sleep(seconds)
            else:
                raise
        except InvalidDcError as e:
            last_error = e
            self._log[__name__].info('Phone migrated to %d', e.new_dc)
            should_raise = isinstance(e, (
                errors.PHONE_MIGRATE, errors.NETWORK_MIGRATE
            ))
            if should_raise and await self.is_user_authorized():
                raise
            await self._switch_dc(e.new_dc)

    if self._raise_last_call_error and last_error is not None:
        raise last_error
    raise ValueError('Request was unsuccessful {} time(s)'
                        .format(attempt))


async def get_me(self: 'TelegramClient', input_peer: bool = False) \
        -> 'typing.Union[_tl.User, _tl.InputPeerUser]':
    try:
        me = (await self(_tl.fn.users.GetUsers([_tl.InputUserSelf()])))[0]
        return utils.get_input_peer(me, allow_self=False) if input_peer else me
    except UnauthorizedError:
        return None

async def is_bot(self: 'TelegramClient') -> bool:
    return self._session_state.bot if self._session_state else False

async def is_user_authorized(self: 'TelegramClient') -> bool:
    if self._authorized is None:
        try:
            # Any request that requires authorization will work
            await self(_tl.fn.updates.GetState())
            self._authorized = True
        except RpcError:
            self._authorized = False

    return self._authorized

async def get_entity(
        self: 'TelegramClient',
        entity: 'hints.EntitiesLike') -> 'hints.Entity':
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

    lists = {
        helpers._EntityType.USER: [],
        helpers._EntityType.CHAT: [],
        helpers._EntityType.CHANNEL: [],
    }
    for x in inputs:
        try:
            lists[helpers._entity_type(x)].append(x)
        except TypeError:
            pass

    users = lists[helpers._EntityType.USER]
    chats = lists[helpers._EntityType.CHAT]
    channels = lists[helpers._EntityType.CHANNEL]
    if users:
        # GetUsers has a limit of 200 per call
        tmp = []
        while users:
            curr, users = users[:200], users[200:]
            tmp.extend(await self(_tl.fn.users.GetUsers(curr)))
        users = tmp
    if chats:  # TODO Handle chats slice?
        chats = (await self(
            _tl.fn.messages.GetChats([x.chat_id for x in chats]))).chats
    if channels:
        channels = (await self(
            _tl.fn.channels.GetChannels(channels))).chats

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
            result.append(await _get_entity_from_string(self, x))
        elif not isinstance(x, _tl.InputPeerSelf):
            result.append(id_entity[utils.get_peer_id(x)])
        else:
            result.append(next(
                u for u in id_entity.values()
                if isinstance(u, _tl.User) and u.is_self
            ))

    return result[0] if single else result

async def get_input_entity(
        self: 'TelegramClient',
        peer: 'hints.EntityLike') -> '_tl.TypeInputPeer':
    # Short-circuit if the input parameter directly maps to an InputPeer
    try:
        return utils.get_input_peer(peer)
    except TypeError:
        pass

    # Next in priority is having a peer (or its ID) cached in-memory
    try:
        # 0x2d45687 == crc32(b'Peer')
        # TODO: FIXME: This logic is incorrect - Peers are unhashable and the cache should be sorted by Entity.ty
        # if isinstance(peer, int) or peer.SUBCLASS_OF_ID == 0x2d45687:
        #     return self._entity_cache[peer]
        pass
    except (AttributeError, KeyError):
        pass

    # Then come known strings that take precedence
    if peer in ('me', 'self'):
        return _tl.InputPeerSelf()

    # No InputPeer, cached peer, or known string. Fetch from session cache
    try:
        peer_id = utils.get_peer_id(peer)
    except TypeError:
        pass
    else:
        entity_type = get_peer_canonical_entity_type(peer)
        entity = await self.session.get_entity(entity_type, peer_id)
        if entity:
            if entity_type == Entity.USER:
                return _tl.InputPeerUser(entity.id, entity.access_hash)
            elif entity_type == Entity.GROUP:
                return _tl.InputPeerChat(peer.chat_id)
            elif entity_type == Entity.CHANNEL:
                return _tl.InputPeerChannel(entity.id, entity.access_hash)

    # Only network left to try
    if isinstance(peer, str):
        return utils.get_input_peer(
            await _get_entity_from_string(self, peer))

    # If we're a bot and the user has messaged us privately users.getUsers
    # will work with access_hash = 0. Similar for channels.getChannels.
    # If we're not a bot but the user is in our contacts, it seems to work
    # regardless. These are the only two special-cased requests.
    peer = utils.get_peer(peer)
    if isinstance(peer, _tl.PeerUser):
        users = await self(_tl.fn.users.GetUsers([
            _tl.InputUser(peer.user_id, access_hash=0)]))
        if users and not isinstance(users[0], _tl.UserEmpty):
            # If the user passed a valid ID they expect to work for
            # channels but would be valid for users, we get UserEmpty.
            # Avoid returning the invalid empty input peer for that.
            #
            # We *could* try to guess if it's a channel first, and if
            # it's not, work as a chat and try to validate it through
            # another request, but that becomes too much work.
            return utils.get_input_peer(users[0])
    elif isinstance(peer, _tl.PeerChat):
        return _tl.InputPeerChat(peer.chat_id)
    elif isinstance(peer, _tl.PeerChannel):
        try:
            channels = await self(_tl.fn.channels.GetChannels([
                _tl.InputChannel(peer.channel_id, access_hash=0)]))
            return utils.get_input_peer(channels.chats[0])
        except errors.CHANNEL_INVALID:
            pass

    raise ValueError(
        'Could not find the input entity for {} ({}). Please read https://'
        'docs.telethon.dev/en/latest/concepts/entities.html to'
        ' find out more details.'
        .format(peer, type(peer).__name__)
    )

async def get_peer_id(
        self: 'TelegramClient',
        peer: 'hints.EntityLike') -> int:
    if isinstance(peer, int):
        return utils.get_peer_id(peer)

    try:
        if peer.SUBCLASS_OF_ID not in (0x2d45687, 0xc91c90b6):
            # 0x2d45687, 0xc91c90b6 == crc32(b'Peer') and b'InputPeer'
            peer = await self.get_input_entity(peer)
    except AttributeError:
        peer = await self.get_input_entity(peer)

    if isinstance(peer, _tl.InputPeerSelf):
        peer = await self.get_me(input_peer=True)

    return utils.get_peer_id(peer)


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
                    _tl.fn.contacts.GetContacts(0))).users:
                if user.phone == phone:
                    return user
        except errors.BOT_METHOD_INVALID:
            raise ValueError('Cannot get entity by phone number as a '
                                'bot (try using integer IDs, not strings)')
    elif string.lower() in ('me', 'self'):
        return await self.get_me()
    else:
        username, is_join_chat = utils.parse_username(string)
        if is_join_chat:
            invite = await self(
                _tl.fn.messages.CheckChatInvite(username))

            if isinstance(invite, _tl.ChatInvite):
                raise ValueError(
                    'Cannot get entity from a channel (or group) '
                    'that you are not part of. Join the group and retry'
                )
            elif isinstance(invite, _tl.ChatInviteAlready):
                return invite.chat
        elif username:
            try:
                result = await self(
                    _tl.fn.contacts.ResolveUsername(username))
            except errors.USERNAME_NOT_OCCUPIED as e:
                raise ValueError('No user has "{}" as username'
                                    .format(username)) from e

            try:
                pid = utils.get_peer_id(result.peer)
                if isinstance(result.peer, _tl.PeerUser):
                    return next(x for x in result.users if x.id == pid)
                else:
                    return next(x for x in result.chats if x.id == pid)
            except StopIteration:
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
            return _tl.InputDialogPeer(dialog)
    except AttributeError:
        pass

    return _tl.InputDialogPeer(await self.get_input_entity(dialog))

async def _get_input_notify(self: 'TelegramClient', notify):
    """
    Returns a :tl:`InputNotifyPeer`. This is a bit tricky because
    it may or not need access to the client to convert what's given
    into an input entity.
    """
    try:
        if notify.SUBCLASS_OF_ID == 0x58981615:
            if isinstance(notify, _tl.InputNotifyPeer):
                notify.peer = await self.get_input_entity(notify.peer)
            return notify
    except AttributeError:
        pass

    return _tl.InputNotifyPeer(await self.get_input_entity(notify))
