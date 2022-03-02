import itertools
import re
import typing

from .._misc import helpers, utils
from ..types import _custom
from ..types._custom.inputmessage import InputMessage
from .. import _tl

if typing.TYPE_CHECKING:
    from .telegramclient import TelegramClient


async def _replace_with_mention(self: 'TelegramClient', entities, i, user):
    """
    Helper method to replace ``entities[i]`` to mention ``user``,
    or do nothing if it can't be found.
    """
    try:
        entities[i] = _tl.InputMessageEntityMentionName(
            entities[i].offset, entities[i].length,
            await self._get_input_peer(user)
        )
        return True
    except (ValueError, TypeError):
        return False

async def _parse_message_text(self: 'TelegramClient', message, parse_mode):
    """
    Returns a (parsed message, entities) tuple depending on ``parse_mode``.
    """
    if parse_mode == ():
        parse, _ = InputMessage._default_parse_mode
    else:
        parse, _ = utils.sanitize_parse_mode(parse_mode)

    original_message = message
    message, msg_entities = parse(message)
    if original_message and not message and not msg_entities:
        raise ValueError("Failed to parse message")

    for i in reversed(range(len(msg_entities))):
        e = msg_entities[i]
        if isinstance(e, _tl.MessageEntityTextUrl):
            m = re.match(r'^@|\+|tg://user\?id=(\d+)', e.url)
            if m:
                user = int(m.group(1)) if m.group(1) else e.url
                is_mention = await _replace_with_mention(self, msg_entities, i, user)
                if not is_mention:
                    del msg_entities[i]
        elif isinstance(e, (_tl.MessageEntityMentionName,
                            _tl.InputMessageEntityMentionName)):
            is_mention = await _replace_with_mention(self, msg_entities, i, e.user_id)
            if not is_mention:
                del msg_entities[i]

    return message, msg_entities

def _get_response_message(self: 'TelegramClient', request, result, input_chat):
    """
    Extracts the response message known a request and Update result.
    The request may also be the ID of the message to match.

    If ``request is None`` this method returns ``{id: message}``.

    If ``request.random_id`` is a list, this method returns a list too.
    """
    if isinstance(result, _tl.UpdateShort):
        updates = [result.update]
        entities = {}
    elif isinstance(result, (_tl.Updates, _tl.UpdatesCombined)):
        updates = result.updates
        entities = {utils.get_peer_id(x): x
                    for x in
                    itertools.chain(result.users, result.chats)}
    else:
        return None

    random_to_id = {}
    id_to_message = {}
    for update in updates:
        if isinstance(update, _tl.UpdateMessageID):
            random_to_id[update.random_id] = update.id

        elif isinstance(update, (
                _tl.UpdateNewChannelMessage, _tl.UpdateNewMessage)):
            message = _custom.Message._new(self, update.message, entities, input_chat)

            # Pinning a message with `updatePinnedMessage` seems to
            # always produce a service message we can't map so return
            # it directly. The same happens for kicking users.
            #
            # It could also be a list (e.g. when sending albums).
            #
            # TODO this method is getting messier and messier as time goes on
            if hasattr(request, 'random_id') or utils.is_list_like(request):
                id_to_message[message.id] = message
            else:
                return message

        elif (isinstance(update, _tl.UpdateEditMessage)
                and helpers._entity_type(request.peer) != helpers._EntityType.CHANNEL):
            message = _custom.Message._new(self, update.message, entities, input_chat)

            # Live locations use `sendMedia` but Telegram responds with
            # `updateEditMessage`, which means we won't have `id` field.
            if hasattr(request, 'random_id'):
                id_to_message[message.id] = message
            elif request.id == message.id:
                return message

        elif (isinstance(update, _tl.UpdateEditChannelMessage)
                and utils.get_peer_id(request.peer) ==
                utils.get_peer_id(update.message.peer_id)):
            if request.id == update.message.id:
                return _custom.Message._new(self, update.message, entities, input_chat)

        elif isinstance(update, _tl.UpdateNewScheduledMessage):
            # Scheduled IDs may collide with normal IDs. However, for a
            # single request there *shouldn't* be a mix between "some
            # scheduled and some not".
            id_to_message[update.message.id] = _custom.Message._new(self, update.message, entities, input_chat)

        elif isinstance(update, _tl.UpdateMessagePoll):
            if request.media.poll.id == update.poll_id:
                return _custom.Message._new(self, _tl.Message(
                    id=request.id,
                    peer_id=utils.get_peer(request.peer),
                    media=_tl.MessageMediaPoll(
                        poll=update.poll,
                        results=update.results
                    ),
                    date=None,
                    message=''
                ), entities, input_chat)

    if request is None:
        return id_to_message

    random_id = request if isinstance(request, (int, list)) else getattr(request, 'random_id', None)
    if random_id is None:
        # Can happen when pinning a message does not actually produce a service message.
        self._log[__name__].warning(
            'No random_id in %s to map to, returning None message for %s', request, result)
        return None

    if not utils.is_list_like(random_id):
        msg = id_to_message.get(random_to_id.get(random_id))

        if not msg:
            self._log[__name__].warning(
                'Request %s had missing message mapping %s', request, result)

        return msg

    try:
        return [id_to_message[random_to_id[rnd]] for rnd in random_id]
    except KeyError:
        # Sometimes forwards fail (`MESSAGE_ID_INVALID` if a message gets
        # deleted or `WORKER_BUSY_TOO_LONG_RETRY` if there are issues at
        # Telegram), in which case we get some "missing" message mappings.
        # Log them with the hope that we can better work around them.
        #
        # This also happens when trying to forward messages that can't
        # be forwarded because they don't exist (0, service, deleted)
        # among others which could be (like deleted or existing).
        self._log[__name__].warning(
            'Request %s had missing message mappings %s', request, result)

    return [
        id_to_message.get(random_to_id[rnd])
        if rnd in random_to_id
        else None
        for rnd in random_id
    ]
