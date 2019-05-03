import itertools
import re
import typing

from .users import UserMethods
from .. import utils
from ..tl import types

if typing.TYPE_CHECKING:
    from .telegramclient import TelegramClient


class MessageParseMethods(UserMethods):

    # region Public properties

    @property
    def parse_mode(self: 'TelegramClient'):
        """
        This property is the default parse mode used when sending messages.
        Defaults to `telethon.extensions.markdown`. It will always
        be either ``None`` or an object with ``parse`` and ``unparse``
        methods.

        When setting a different value it should be one of:

        * Object with ``parse`` and ``unparse`` methods.
        * A ``callable`` to act as the parse method.
        * A ``str`` indicating the ``parse_mode``. For Markdown ``'md'``
          or ``'markdown'`` may be used. For HTML, ``'htm'`` or ``'html'``
          may be used.

        The ``parse`` method should be a function accepting a single
        parameter, the text to parse, and returning a tuple consisting
        of ``(parsed message str, [MessageEntity instances])``.

        The ``unparse`` method should be the inverse of ``parse`` such
        that ``assert text == unparse(*parse(text))``.

        See :tl:`MessageEntity` for allowed message entities.
        """
        return self._parse_mode

    @parse_mode.setter
    def parse_mode(self: 'TelegramClient', mode: str):
        self._parse_mode = utils.sanitize_parse_mode(mode)

    # endregion

    # region Private methods

    async def _replace_with_mention(self: 'TelegramClient', entities, i, user):
        """
        Helper method to replace ``entities[i]`` to mention ``user``,
        or do nothing if it can't be found.
        """
        try:
            entities[i] = types.InputMessageEntityMentionName(
                entities[i].offset, entities[i].length,
                await self.get_input_entity(user)
            )
            return True            
        except (ValueError, TypeError):
            return False

    async def _parse_message_text(self: 'TelegramClient', message, parse_mode):
        """
        Returns a (parsed message, entities) tuple depending on ``parse_mode``.
        """
        if parse_mode is ():
            parse_mode = self._parse_mode
        else:
            parse_mode = utils.sanitize_parse_mode(parse_mode)

        if not parse_mode:
            return message, []

        message, msg_entities = parse_mode.parse(message)
        for i in reversed(range(len(msg_entities))):
            e = msg_entities[i]
            if isinstance(e, types.MessageEntityTextUrl):
                m = re.match(r'^@|\+|tg://user\?id=(\d+)', e.url)
                if m:
                    user = int(m.group(1)) if m.group(1) else e.url
                    is_mention = await self._replace_with_mention(msg_entities, i, user)
                    if not is_mention:
                        del msg_entities[i]
            elif isinstance(e, (types.MessageEntityMentionName,
                                types.InputMessageEntityMentionName)):
                is_mention = await self._replace_with_mention(msg_entities, i, e.user_id)
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
        if isinstance(result, types.UpdateShort):
            updates = [result.update]
            entities = {}
        elif isinstance(result, (types.Updates, types.UpdatesCombined)):
            updates = result.updates
            entities = {utils.get_peer_id(x): x
                        for x in
                        itertools.chain(result.users, result.chats)}
        else:
            return None

        random_to_id = {}
        id_to_message = {}
        for update in updates:
            if isinstance(update, types.UpdateMessageID):
                random_to_id[update.random_id] = update.id

            elif isinstance(update, (
                    types.UpdateNewChannelMessage, types.UpdateNewMessage)):
                update.message._finish_init(self, entities, input_chat)
                id_to_message[update.message.id] = update.message

            elif (isinstance(update, types.UpdateEditMessage)
                  and not isinstance(request.peer, types.InputPeerChannel)):
                if request.id == update.message.id:
                    update.message._finish_init(self, entities, input_chat)
                    return update.message

            elif (isinstance(update, types.UpdateEditChannelMessage)
                  and utils.get_peer_id(request.peer) ==
                  utils.get_peer_id(update.message.to_id)):
                if request.id == update.message.id:
                    update.message._finish_init(self, entities, input_chat)
                    return update.message

        if request is None:
            return id_to_message

        random_id = request if isinstance(request, int) else request.random_id
        if not utils.is_list_like(random_id):
            if random_id in random_to_id:
                return id_to_message[random_to_id[random_id]]
            else:
                return None
        else:
            # ``rnd in random_to_id`` is needed because trying to forward only
            # deleted messages causes `MESSAGE_ID_INVALID`, but forwarding
            # valid and invalid messages in the same call makes the call
            # succeed, although the API won't return those messages thus
            # `random_to_id[rnd]` would `KeyError`.
            return [id_to_message[random_to_id[rnd]]
                    if rnd in random_to_id else None
                    for rnd in random_id]

    # endregion
