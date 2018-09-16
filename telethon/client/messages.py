import asyncio
import itertools
import logging
import time

from async_generator import async_generator, yield_

from .messageparse import MessageParseMethods
from .uploads import UploadMethods
from .buttons import ButtonMethods
from .. import utils, helpers
from ..tl import types, functions, custom

__log__ = logging.getLogger(__name__)


class MessageMethods(UploadMethods, ButtonMethods, MessageParseMethods):

    # region Public methods

    # region Message retrieval

    @async_generator
    async def iter_messages(
            self, entity, limit=None, *, offset_date=None, offset_id=0,
            max_id=0, min_id=0, add_offset=0, search=None, filter=None,
            from_user=None, batch_size=100, wait_time=None, ids=None,
            reverse=False, _total=None):
        """
        Iterator over the message history for the specified entity.

        If either `search`, `filter` or `from_user` are provided,
        :tl:`messages.Search` will be used instead of :tl:`messages.getHistory`.

        Args:
            entity (`entity`):
                The entity from whom to retrieve the message history.

                It may be ``None`` to perform a global search, or
                to get messages by their ID from no particular chat.
                Note that some of the offsets will not work if this
                is the case.

                Note that if you want to perform a global search,
                you **must** set a non-empty `search` string.

            limit (`int` | `None`, optional):
                Number of messages to be retrieved. Due to limitations with
                the API retrieving more than 3000 messages will take longer
                than half a minute (or even more based on previous calls).
                The limit may also be ``None``, which would eventually return
                the whole history.

            offset_date (`datetime`):
                Offset date (messages *previous* to this date will be
                retrieved). Exclusive.

            offset_id (`int`):
                Offset message ID (only messages *previous* to the given
                ID will be retrieved). Exclusive.

            max_id (`int`):
                All the messages with a higher (newer) ID or equal to this will
                be excluded.

            min_id (`int`):
                All the messages with a lower (older) ID or equal to this will
                be excluded.

            add_offset (`int`):
                Additional message offset (all of the specified offsets +
                this offset = older messages).

            search (`str`):
                The string to be used as a search query.

            filter (:tl:`MessagesFilter` | `type`):
                The filter to use when returning messages. For instance,
                :tl:`InputMessagesFilterPhotos` would yield only messages
                containing photos.

            from_user (`entity`):
                Only messages from this user will be returned.

            batch_size (`int`):
                Messages will be returned in chunks of this size (100 is
                the maximum). While it makes no sense to modify this value,
                you are still free to do so.

            wait_time (`int`):
                Wait time between different :tl:`GetHistoryRequest`. Use this
                parameter to avoid hitting the ``FloodWaitError`` as needed.
                If left to ``None``, it will default to 1 second only if
                the limit is higher than 3000.

            ids (`int`, `list`):
                A single integer ID (or several IDs) for the message that
                should be returned. This parameter takes precedence over
                the rest (which will be ignored if this is set). This can
                for instance be used to get the message with ID 123 from
                a channel. Note that if the message doesn't exist, ``None``
                will appear in its place, so that zipping the list of IDs
                with the messages can match one-to-one.

            reverse (`bool`, optional):
                If set to ``True``, the messages will be returned in reverse
                order (from oldest to newest, instead of the default newest
                to oldest). This also means that the meaning of `offset_id`
                and `offset_date` parameters is reversed, although they will
                still be exclusive. `min_id` becomes equivalent to `offset_id`
                instead of being `max_id` as well since messages are returned
                in ascending order.

                You cannot use this if both `entity` and `ids` are ``None``.

            _total (`list`, optional):
                A single-item list to pass the total parameter by reference.

        Yields:
            Instances of `telethon.tl.custom.message.Message`.

        Notes:
            Telegram's flood wait limit for :tl:`GetHistoryRequest` seems to
            be around 30 seconds per 3000 messages, therefore a sleep of 1
            second is the default for this limit (or above). You may need
            an higher limit, so you're free to set the ``batch_size`` that
            you think may be good.
        """
        # Note that entity being ``None`` is intended to get messages by
        # ID under no specific chat, and also to request a global search.
        if entity:
            entity = await self.get_input_entity(entity)

        if ids:
            if not utils.is_list_like(ids):
                ids = (ids,)
            if reverse:
                ids = list(reversed(ids))
            async for x in self._iter_ids(entity, ids, total=_total):
                await yield_(x)
            return

        # Telegram doesn't like min_id/max_id. If these IDs are low enough
        # (starting from last_id - 100), the request will return nothing.
        #
        # We can emulate their behaviour locally by setting offset = max_id
        # and simply stopping once we hit a message with ID <= min_id.
        if reverse:
            offset_id = max(offset_id, min_id)
            if offset_id and max_id:
                if max_id - offset_id <= 1:
                    return

            if not max_id:
                max_id = float('inf')
        else:
            offset_id = max(offset_id, max_id)
            if offset_id and min_id:
                if offset_id - min_id <= 1:
                    return

        if reverse:
            if offset_id:
                offset_id += 1
            else:
                offset_id = 1

        from_id = None
        limit = float('inf') if limit is None else int(limit)
        if not entity:
            if reverse:
                raise ValueError('Cannot reverse global search')

            reverse = None
            request = functions.messages.SearchGlobalRequest(
                q=search or '',
                offset_date=offset_date,
                offset_peer=types.InputPeerEmpty(),
                offset_id=offset_id,
                limit=1
            )
        elif search is not None or filter or from_user:
            if filter is None:
                filter = types.InputMessagesFilterEmpty()
            request = functions.messages.SearchRequest(
                peer=entity,
                q=search or '',
                filter=filter() if isinstance(filter, type) else filter,
                min_date=None,
                max_date=offset_date,
                offset_id=offset_id,
                add_offset=add_offset,
                limit=0,  # Search actually returns 0 items if we ask it to
                max_id=0,
                min_id=0,
                hash=0,
                from_id=(
                    await self.get_input_entity(from_user)
                    if from_user else None
                )
            )
            if isinstance(entity, types.InputPeerUser):
                # Telegram completely ignores `from_id` in private
                # chats, so we need to do this check client-side.
                if isinstance(request.from_id, types.InputPeerSelf):
                    from_id = (await self.get_me(input_peer=True)).user_id
                else:
                    from_id = request.from_id
        else:
            request = functions.messages.GetHistoryRequest(
                peer=entity,
                limit=1,
                offset_date=offset_date,
                offset_id=offset_id,
                min_id=0,
                max_id=0,
                add_offset=add_offset,
                hash=0
            )

        if limit == 0:
            if not _total:
                return
            # No messages, but we still need to know the total message count
            result = await self(request)
            if isinstance(result, types.messages.MessagesNotModified):
                _total[0] = result.count
            else:
                _total[0] = getattr(result, 'count', len(result.messages))
            return

        if wait_time is None:
            wait_time = 1 if limit > 3000 else 0

        have = 0
        last_id = 0 if reverse else float('inf')

        # Telegram has a hard limit of 100.
        # We don't need to fetch 100 if the limit is less.
        batch_size = min(max(batch_size, 1), min(100, limit))

        # Use a negative offset to work around reversing the results
        if reverse:
            request.add_offset -= batch_size

        while have < limit:
            start = time.time()

            request.limit = min(limit - have, batch_size)
            if reverse and request.limit != batch_size:
                # Last batch needs special care if we're on reverse
                request.add_offset += batch_size - request.limit + 1

            r = await self(request)
            if _total:
                _total[0] = getattr(r, 'count', len(r.messages))

            entities = {utils.get_peer_id(x): x
                        for x in itertools.chain(r.users, r.chats)}

            messages = reversed(r.messages) if reverse else r.messages
            for message in messages:
                if (isinstance(message, types.MessageEmpty)
                        or from_id and message.from_id != from_id):
                    continue

                if reverse is None:
                    pass
                elif reverse:
                    if message.id <= last_id or message.id >= max_id:
                        return
                else:
                    if message.id >= last_id or message.id <= min_id:
                        return

                # There has been reports that on bad connections this method
                # was returning duplicated IDs sometimes. Using ``last_id``
                # is an attempt to avoid these duplicates, since the message
                # IDs are returned in descending order (or asc if reverse).
                last_id = message.id

                message._finish_init(self, entities, entity)
                await yield_(message)
                have += 1

            if len(r.messages) < request.limit:
                break

            # Find the first message that's not empty (in some rare cases
            # it can happen that the last message is :tl:`MessageEmpty`)
            last_message = None
            messages = r.messages if reverse else reversed(r.messages)
            for m in messages:
                if not isinstance(m, types.MessageEmpty):
                    last_message = m
                    break

            if last_message is None:
                # There are some cases where all the messages we get start
                # being empty. This can happen on migrated mega-groups if
                # the history was cleared, and we're using search. Telegram
                # acts incredibly weird sometimes. Messages are returned but
                # only "empty", not their contents. If this is the case we
                # should just give up since there won't be any new Message.
                break
            else:
                request.offset_id = last_message.id
                if isinstance(request, functions.messages.SearchRequest):
                    request.max_date = last_message.date
                else:
                    # getHistory and searchGlobal call it offset_date
                    request.offset_date = last_message.date

                if isinstance(request, functions.messages.SearchGlobalRequest):
                    request.offset_peer = last_message.input_chat
                elif reverse:
                    # We want to skip the one we already have
                    request.add_offset -= 1

            await asyncio.sleep(
                max(wait_time - (time.time() - start), 0), loop=self._loop)

    async def get_messages(self, *args, **kwargs):
        """
        Same as `iter_messages`, but returns a
        `TotalList <telethon.helpers.TotalList>` instead.

        If the `limit` is not set, it will be 1 by default unless both
        `min_id` **and** `max_id` are set (as *named* arguments), in
        which case the entire range will be returned.

        This is so because any integer limit would be rather arbitrary and
        it's common to only want to fetch one message, but if a range is
        specified it makes sense that it should return the entirety of it.

        If `ids` is present in the *named* arguments and is not a list,
        a single :tl:`Message` will be returned for convenience instead
        of a list.
        """
        total = [0]
        kwargs['_total'] = total
        if len(args) == 1 and 'limit' not in kwargs:
            if 'min_id' in kwargs and 'max_id' in kwargs:
                kwargs['limit'] = None
            else:
                kwargs['limit'] = 1

        msgs = helpers.TotalList()
        async for x in self.iter_messages(*args, **kwargs):
            msgs.append(x)
        msgs.total = total[0]
        if 'ids' in kwargs and not utils.is_list_like(kwargs['ids']):
            return msgs[0]

        return msgs

    # endregion

    # region Message sending/editing/deleting

    async def send_message(
            self, entity, message='', *, reply_to=None,
            parse_mode=utils.Default, link_preview=True, file=None,
            force_document=False, clear_draft=False, buttons=None,
            silent=None):
        """
        Sends the given message to the specified entity (user/chat/channel).

        The default parse mode is the same as the official applications
        (a custom flavour of markdown). ``**bold**, `code` or __italic__``
        are available. In addition you can send ``[links](https://example.com)``
        and ``[mentions](@username)`` (or using IDs like in the Bot API:
        ``[mention](tg://user?id=123456789)``) and ``pre`` blocks with three
        backticks.

        Sending a ``/start`` command with a parameter (like ``?start=data``)
        is also done through this method. Simply send ``'/start data'`` to
        the bot.

        Args:
            entity (`entity`):
                To who will it be sent.

            message (`str` | :tl:`Message`):
                The message to be sent, or another message object to resend.

                The maximum length for a message is 35,000 bytes or 4,096
                characters. Longer messages will not be sliced automatically,
                and you should slice them manually if the text to send is
                longer than said length.

            reply_to (`int` | :tl:`Message`, optional):
                Whether to reply to a message or not. If an integer is provided,
                it should be the ID of the message that it should reply to.

            parse_mode (`object`, optional):
                See the `TelegramClient.parse_mode` property for allowed
                values. Markdown parsing will be used by default.

            link_preview (`bool`, optional):
                Should the link preview be shown?

            file (`file`, optional):
                Sends a message with a file attached (e.g. a photo,
                video, audio or document). The ``message`` may be empty.

            force_document (`bool`, optional):
                Whether to send the given file as a document or not.

            clear_draft (`bool`, optional):
                Whether the existing draft should be cleared or not.
                Has no effect when sending a file.

            buttons (`list`, `custom.Button <telethon.tl.custom.button.Button>`,
            :tl:`KeyboardButton`):
                The matrix (list of lists), row list or button to be shown
                after sending the message. This parameter will only work if
                you have signed in as a bot. You can also pass your own
                :tl:`ReplyMarkup` here.

                All the following limits apply together:

                * There can be 100 buttons at most (any more are ignored).
                * There can be 8 buttons per row at most (more are ignored).
                * The maximum callback data per button is 64 bytes.
                * The maximum data that can be embedded in total is just
                  over 4KB, shared between inline callback data and text.

            silent (`bool`, optional):
                Whether the message should notify people in a broadcast
                channel or not. Defaults to ``False``, which means it will
                notify them. Set it to ``True`` to alter this behaviour.

        Returns:
            The sent `custom.Message <telethon.tl.custom.message.Message>`.
        """
        if file is not None:
            return await self.send_file(
                entity, file, caption=message, reply_to=reply_to,
                parse_mode=parse_mode, force_document=force_document,
                buttons=buttons
            )
        elif not message:
            raise ValueError(
                'The message cannot be empty unless a file is provided'
            )

        entity = await self.get_input_entity(entity)
        if isinstance(message, types.Message):
            if buttons is None:
                markup = message.reply_markup
            else:
                markup = self.build_reply_markup(buttons)

            if silent is None:
                silent = message.silent

            if (message.media and not isinstance(
                    message.media, types.MessageMediaWebPage)):
                return await self.send_file(
                    entity,
                    message.media,
                    caption=message.message,
                    silent=silent,
                    reply_to=reply_to,
                    buttons=markup,
                    entities=message.entities
                )

            request = functions.messages.SendMessageRequest(
                peer=entity,
                message=message.message or '',
                silent=silent,
                reply_to_msg_id=utils.get_message_id(reply_to),
                reply_markup=markup,
                entities=message.entities,
                clear_draft=clear_draft,
                no_webpage=not isinstance(
                    message.media, types.MessageMediaWebPage)
            )
            message = message.message
        else:
            message, msg_ent = await self._parse_message_text(message,
                                                              parse_mode)
            request = functions.messages.SendMessageRequest(
                peer=entity,
                message=message,
                entities=msg_ent,
                no_webpage=not link_preview,
                reply_to_msg_id=utils.get_message_id(reply_to),
                clear_draft=clear_draft,
                silent=silent,
                reply_markup=self.build_reply_markup(buttons)
            )

        result = await self(request)
        if isinstance(result, types.UpdateShortSentMessage):
            to_id, cls = utils.resolve_id(utils.get_peer_id(entity))
            message = types.Message(
                id=result.id,
                to_id=cls(to_id),
                message=message,
                date=result.date,
                out=result.out,
                media=result.media,
                entities=result.entities
            )
            message._finish_init(self, {}, entity)
            return message

        return self._get_response_message(request, result, entity)

    async def forward_messages(self, entity, messages, from_peer=None,
                               *, silent=None):
        """
        Forwards the given message(s) to the specified entity.

        Args:
            entity (`entity`):
                To which entity the message(s) will be forwarded.

            messages (`list` | `int` | :tl:`Message`):
                The message(s) to forward, or their integer IDs.

            from_peer (`entity`):
                If the given messages are integer IDs and not instances
                of the ``Message`` class, this *must* be specified in
                order for the forward to work.

            silent (`bool`, optional):
                Whether the message should notify people in a broadcast
                channel or not. Defaults to ``False``, which means it will
                notify them. Set it to ``True`` to alter this behaviour.

        Returns:
            The list of forwarded `telethon.tl.custom.message.Message`,
            or a single one if a list wasn't provided as input.
        """
        single = not utils.is_list_like(messages)
        if single:
            messages = (messages,)

        if not from_peer:
            try:
                # On private chats (to_id = PeerUser), if the message is
                # not outgoing, we actually need to use "from_id" to get
                # the conversation on which the message was sent.
                from_peer = next(
                    m.from_id
                    if not m.out and isinstance(m.to_id, types.PeerUser)
                    else m.to_id for m in messages
                    if isinstance(m, types.Message)
                )
            except StopIteration:
                raise ValueError(
                    'from_chat must be given if integer IDs are used'
                )

        req = functions.messages.ForwardMessagesRequest(
            from_peer=from_peer,
            id=[m if isinstance(m, int) else m.id for m in messages],
            to_peer=entity,
            silent=silent
        )
        result = await self(req)
        if isinstance(result, (types.Updates, types.UpdatesCombined)):
            entities = {utils.get_peer_id(x): x
                        for x in itertools.chain(result.users, result.chats)}
        else:
            entities = {}

        random_to_id = {}
        id_to_message = {}
        for update in result.updates:
            if isinstance(update, types.UpdateMessageID):
                random_to_id[update.random_id] = update.id
            elif isinstance(update, (
                    types.UpdateNewMessage, types.UpdateNewChannelMessage)):
                update.message._finish_init(self, entities, entity)
                id_to_message[update.message.id] = update.message

        result = [id_to_message[random_to_id[rnd]] for rnd in req.random_id]
        return result[0] if single else result

    async def edit_message(
            self, entity, message=None, text=None,
            *, parse_mode=utils.Default, link_preview=True, file=None,
            buttons=None):
        """
        Edits the given message ID (to change its contents or disable preview).

        Args:
            entity (`entity` | :tl:`Message`):
                From which chat to edit the message. This can also be
                the message to be edited, and the entity will be inferred
                from it, so the next parameter will be assumed to be the
                message text.

            message (`int` | :tl:`Message` | `str`):
                The ID of the message (or :tl:`Message` itself) to be edited.
                If the `entity` was a :tl:`Message`, then this message will be
                treated as the new text.

            text (`str`, optional):
                The new text of the message. Does nothing if the `entity`
                was a :tl:`Message`.

            parse_mode (`object`, optional):
                See the `TelegramClient.parse_mode` property for allowed
                values. Markdown parsing will be used by default.

            link_preview (`bool`, optional):
                Should the link preview be shown?

            file (`str` | `bytes` | `file` | `media`, optional):
                The file object that should replace the existing media
                in the message.

            buttons (`list`, `custom.Button <telethon.tl.custom.button.Button>`,
            :tl:`KeyboardButton`):
                The matrix (list of lists), row list or button to be shown
                after sending the message. This parameter will only work if
                you have signed in as a bot. You can also pass your own
                :tl:`ReplyMarkup` here.

        Examples:

            >>> client = ...
            >>> message = client.send_message('username', 'hello')
            >>>
            >>> client.edit_message('username', message, 'hello!')
            >>> # or
            >>> client.edit_message('username', message.id, 'Hello')
            >>> # or
            >>> client.edit_message(message, 'Hello!')

        Raises:
            ``MessageAuthorRequiredError`` if you're not the author of the
            message but tried editing it anyway.

            ``MessageNotModifiedError`` if the contents of the message were
            not modified at all.

        Returns:
            The edited `telethon.tl.custom.message.Message`.
        """
        if isinstance(entity, types.Message):
            text = message  # Shift the parameters to the right
            message = entity
            entity = entity.to_id

        entity = await self.get_input_entity(entity)
        text, msg_entities = await self._parse_message_text(text, parse_mode)
        file_handle, media = await self._file_to_media(file)
        request = functions.messages.EditMessageRequest(
            peer=entity,
            id=utils.get_message_id(message),
            message=text,
            no_webpage=not link_preview,
            entities=msg_entities,
            media=media,
            reply_markup=self.build_reply_markup(buttons)
        )
        msg = self._get_response_message(request, await self(request), entity)
        self._cache_media(msg, file, file_handle)
        return msg

    async def delete_messages(self, entity, message_ids, *, revoke=True):
        """
        Deletes a message from a chat, optionally "for everyone".

        Args:
            entity (`entity`):
                From who the message will be deleted. This can actually
                be ``None`` for normal chats, but **must** be present
                for channels and megagroups.

            message_ids (`list` | `int` | :tl:`Message`):
                The IDs (or ID) or messages to be deleted.

            revoke (`bool`, optional):
                Whether the message should be deleted for everyone or not.
                By default it has the opposite behaviour of official clients,
                and it will delete the message for everyone.
                This has no effect on channels or megagroups.

        Returns:
            A list of :tl:`AffectedMessages`, each item being the result
            for the delete calls of the messages in chunks of 100 each.
        """
        if not utils.is_list_like(message_ids):
            message_ids = (message_ids,)

        message_ids = (
            m.id if isinstance(m, (
                types.Message, types.MessageService, types.MessageEmpty))
            else int(m) for m in message_ids
        )

        entity = await self.get_input_entity(entity) if entity else None
        if isinstance(entity, types.InputPeerChannel):
            return await self([functions.channels.DeleteMessagesRequest(
                         entity, list(c)) for c in utils.chunks(message_ids)])
        else:
            return await self([functions.messages.DeleteMessagesRequest(
                         list(c), revoke) for c in utils.chunks(message_ids)])

    # endregion

    # region Miscellaneous

    async def send_read_acknowledge(
            self, entity, message=None, *, max_id=None, clear_mentions=False):
        """
        Sends a "read acknowledge" (i.e., notifying the given peer that we've
        read their messages, also known as the "double check").

        This effectively marks a message as read (or more than one) in the
        given conversation.

        Args:
            entity (`entity`):
                The chat where these messages are located.

            message (`list` | :tl:`Message`):
                Either a list of messages or a single message.

            max_id (`int`):
                Overrides messages, until which message should the
                acknowledge should be sent.

            clear_mentions (`bool`):
                Whether the mention badge should be cleared (so that
                there are no more mentions) or not for the given entity.

                If no message is provided, this will be the only action
                taken.
        """
        if max_id is None:
            if message:
                if utils.is_list_like(message):
                    max_id = max(msg.id for msg in message)
                else:
                    max_id = message.id
            elif not clear_mentions:
                raise ValueError(
                    'Either a message list or a max_id must be provided.')

        entity = await self.get_input_entity(entity)
        if clear_mentions:
            await self(functions.messages.ReadMentionsRequest(entity))
            if max_id is None:
                return True

        if max_id is not None:
            if isinstance(entity, types.InputPeerChannel):
                return await self(functions.channels.ReadHistoryRequest(
                    entity, max_id=max_id))
            else:
                return await self(functions.messages.ReadHistoryRequest(
                    entity, max_id=max_id))

        return False

    # endregion

    # endregion

    # region Private methods

    @async_generator
    async def _iter_ids(self, entity, ids, total):
        """
        Special case for `iter_messages` when it should only fetch some IDs.
        """
        if total:
            total[0] = len(ids)

        from_id = None  # By default, no need to validate from_id
        if isinstance(entity, (types.InputChannel, types.InputPeerChannel)):
            r = await self(functions.channels.GetMessagesRequest(entity, ids))
        else:
            r = await self(functions.messages.GetMessagesRequest(ids))
            if entity:
                from_id = utils.get_peer_id(entity)

        if isinstance(r, types.messages.MessagesNotModified):
            for _ in ids:
                await yield_(None)
            return

        entities = {utils.get_peer_id(x): x
                    for x in itertools.chain(r.users, r.chats)}

        # Telegram seems to return the messages in the order in which
        # we asked them for, so we don't need to check it ourselves.
        #
        # The passed message IDs may not belong to the desired entity
        # since the user can enter arbitrary numbers which can belong to
        # arbitrary chats. Validate these unless ``from_id is None``.
        for message in r.messages:
            if isinstance(message, types.MessageEmpty) or (
                    from_id and message.chat_id != from_id):
                await yield_(None)
            else:
                message._finish_init(self, entities, entity)
                await yield_(message)

    # endregion
