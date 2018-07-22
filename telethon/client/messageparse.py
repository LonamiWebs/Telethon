import itertools
import re

from .users import UserMethods
from .. import utils
from ..tl import types, custom


class MessageParseMethods(UserMethods):

    # region Public properties

    @property
    def parse_mode(self):
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
    def parse_mode(self, mode):
        self._parse_mode = utils.sanitize_parse_mode(mode)

    # endregion

    # region Private methods

    async def _replace_with_mention(self, entities, i, user):
        """
        Helper method to replace ``entities[i]`` to mention ``user``,
        or do nothing if it can't be found.
        """
        try:
            entities[i] = types.InputMessageEntityMentionName(
                entities[i].offset, entities[i].length,
                await self.get_input_entity(user)
            )
        except (ValueError, TypeError):
            pass

    async def _parse_message_text(self, message, parse_mode):
        """
        Returns a (parsed message, entities) tuple depending on ``parse_mode``.
        """
        if parse_mode == utils.Default:
            parse_mode = self._parse_mode
        else:
            parse_mode = utils.sanitize_parse_mode(parse_mode)

        if not parse_mode:
            return message, []

        message, msg_entities = parse_mode.parse(message)
        for i, e in enumerate(msg_entities):
            if isinstance(e, types.MessageEntityTextUrl):
                m = re.match(r'^@|\+|tg://user\?id=(\d+)', e.url)
                if m:
                    user = int(m.group(1)) if m.group(1) else e.url
                    await self._replace_with_mention(msg_entities, i, user)
            elif isinstance(e, (types.MessageEntityMentionName,
                                types.InputMessageEntityMentionName)):
                await self._replace_with_mention(msg_entities, i, e.user_id)

        return message, msg_entities

    def _get_response_message(self, request, result, input_chat):
        """
        Extracts the response message known a request and Update result.
        The request may also be the ID of the message to match.
        """
        # Telegram seems to send updateMessageID first, then updateNewMessage,
        # however let's not rely on that just in case.
        if isinstance(request, int):
            msg_id = request
        else:
            msg_id = None
            for update in result.updates:
                if isinstance(update, types.UpdateMessageID):
                    if update.random_id == request.random_id:
                        msg_id = update.id
                        break

        if isinstance(result, types.UpdateShort):
            updates = [result.update]
            entities = {}
        elif isinstance(result, (types.Updates, types.UpdatesCombined)):
            updates = result.updates
            entities = {utils.get_peer_id(x): x
                        for x in
                        itertools.chain(result.users, result.chats)}
        else:
            return

        found = None
        for update in updates:
            if isinstance(update, (
                    types.UpdateNewChannelMessage, types.UpdateNewMessage)):
                if update.message.id == msg_id:
                    found = update.message
                    break

            elif (isinstance(update, types.UpdateEditMessage)
                  and not isinstance(request.peer, types.InputPeerChannel)):
                if request.id == update.message.id:
                    found = update.message
                    break

            elif (isinstance(update, types.UpdateEditChannelMessage)
                  and utils.get_peer_id(request.peer) ==
                    utils.get_peer_id(update.message.to_id)):
                if request.id == update.message.id:
                    found = update.message
                    break

        if found:
            found._finish_init(self, entities, input_chat)
            return found

    # endregion
