import asyncio
import datetime
import itertools
import time
import typing

from .. import errors, helpers, utils, hints, _tl
from ..errors import MultiError, RPCError
from ..helpers import retry_range

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


async def call(self: 'TelegramClient', sender, request, ordered=False, flood_sleep_threshold=None):
    if flood_sleep_threshold is None:
        flood_sleep_threshold = self.flood_sleep_threshold
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
            elif diff <= flood_sleep_threshold:
                self._log[__name__].info(*_fmt_flood(diff, r, early=True))
                await asyncio.sleep(diff)
                self._flood_waited_requests.pop(r.CONSTRUCTOR_ID, None)
            else:
                raise errors.FloodWaitError(request=r, capture=diff)

        if self._no_updates:
            r = _tl.fn.InvokeWithoutUpdates(r)

    request_index = 0
    last_error = None
    self._last_request = time.time()

    for attempt in retry_range(self._request_retries):
        try:
            future = sender.send(request, ordered=ordered)
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
                errors.RpcMcgetFailError, errors.InterdcCallErrorError,
                errors.InterdcCallRichErrorError) as e:
            last_error = e
            self._log[__name__].warning(
                'Telegram is having internal issues %s: %s',
                e.__class__.__name__, e)

            await asyncio.sleep(2)
        except (errors.FloodWaitError, errors.SlowModeWaitError, errors.FloodTestPhoneWaitError) as e:
            last_error = e
            if utils.is_list_like(request):
                request = request[request_index]

            # SLOW_MODE_WAIT is chat-specific, not request-specific
            if not isinstance(e, errors.SlowModeWaitError):
                self._flood_waited_requests\
                    [request.CONSTRUCTOR_ID] = time.time() + e.seconds

            # In test servers, FLOOD_WAIT_0 has been observed, and sleeping for
            # such a short amount will cause retries very fast leading to issues.
            if e.seconds == 0:
                e.seconds = 1

            if e.seconds <= self.flood_sleep_threshold:
                self._log[__name__].info(*_fmt_flood(e.seconds, request))
                await asyncio.sleep(e.seconds)
            else:
                raise
        except (errors.PhoneMigrateError, errors.NetworkMigrateError,
                errors.UserMigrateError) as e:
            last_error = e
            self._log[__name__].info('Phone migrated to %d', e.new_dc)
            should_raise = isinstance(e, (
                errors.PhoneMigrateError, errors.NetworkMigrateError
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
    if input_peer and self._self_input_peer:
        return self._self_input_peer

    try:
        me = (await self(
            _tl.fn.users.GetUsers([_tl.InputUserSelf()])))[0]

        self._bot = me.bot
        if not self._self_input_peer:
            self._self_input_peer = utils.get_input_peer(
                me, allow_self=False
            )

        return self._self_input_peer if input_peer else me
    except errors.UnauthorizedError:
        return None

def _self_id(self: 'TelegramClient') -> typing.Optional[int]:
    """
    Returns the ID of the logged-in user, if known.

    This property is used in every update, and some like `updateLoginToken`
    occur prior to login, so it gracefully handles when no ID is known yet.
    """
    return self._self_input_peer.user_id if self._self_input_peer else None

async def is_bot(self: 'TelegramClient') -> bool:
    if self._bot is None:
        self._bot = (await self.get_me()).bot

    return self._bot

async def is_user_authorized(self: 'TelegramClient') -> bool:
    if self._authorized is None:
        try:
            # Any request that requires authorization will work
            await self(_tl.fn.updates.GetState())
            self._authorized = True
        except errors.RPCError:
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
        # GetUsersRequest has a limit of 200 per call
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
            result.append(await self._get_entity_from_string(x))
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
        if isinstance(peer, int) or peer.SUBCLASS_OF_ID == 0x2d45687:
            return self._entity_cache[peer]
    except (AttributeError, KeyError):
        pass

    # Then come known strings that take precedence
    if peer in ('me', 'self'):
        return _tl.InputPeerSelf()

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
        except errors.ChannelInvalidError:
            pass

    raise ValueError(
        'Could not find the input entity for {} ({}). Please read https://'
        'docs.telethon.dev/en/latest/concepts/entities.html to'
        ' find out more details.'
        .format(peer, type(peer).__name__)
    )

async def _get_peer(self: 'TelegramClient', peer: 'hints.EntityLike'):
    i, cls = utils.resolve_id(await self.get_peer_id(peer))
    return cls(i)

async def get_peer_id(
        self: 'TelegramClient',
        peer: 'hints.EntityLike',
        add_mark: bool = True) -> int:
    if isinstance(peer, int):
        return utils.get_peer_id(peer, add_mark=add_mark)

    try:
        if peer.SUBCLASS_OF_ID not in (0x2d45687, 0xc91c90b6):
            # 0x2d45687, 0xc91c90b6 == crc32(b'Peer') and b'InputPeer'
            peer = await self.get_input_entity(peer)
    except AttributeError:
        peer = await self.get_input_entity(peer)

    if isinstance(peer, _tl.InputPeerSelf):
        peer = await self.get_me(input_peer=True)

    return utils.get_peer_id(peer, add_mark=add_mark)


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
        except errors.BotMethodInvalidError:
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
            except errors.UsernameNotOccupiedError as e:
                raise ValueError('No user has "{}" as username'
                                    .format(username)) from e

            try:
                pid = utils.get_peer_id(result.peer, add_mark=False)
                if isinstance(result.peer, _tl.PeerUser):
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
