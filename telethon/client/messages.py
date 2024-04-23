import inspect
import itertools
import typing
import warnings

from .. import helpers, utils, errors, hints
from ..requestiter import RequestIter
from ..tl import types, functions

_MAX_CHUNK_SIZE = 100

if typing.TYPE_CHECKING:
    from .telegramclient import TelegramClient


class _MessagesIter(RequestIter):
    """
    Common factor for all requests that need to iterate over messages.
    """
    async def _init(
            self, entity, offset_id, min_id, max_id,
            from_user, offset_date, add_offset, filter, search, reply_to,
            scheduled
    ):
        # Note that entity being `None` will perform a global search.
        if entity:
            self.entity = await self.client.get_input_entity(entity)
        else:
            self.entity = None
            if self.reverse:
                raise ValueError('Cannot reverse global search')

        # Telegram doesn't like min_id/max_id. If these IDs are low enough
        # (starting from last_id - 100), the request will return nothing.
        #
        # We can emulate their behaviour locally by setting offset = max_id
        # and simply stopping once we hit a message with ID <= min_id.
        if self.reverse:
            offset_id = max(offset_id, min_id)
            if offset_id and max_id:
                if max_id - offset_id <= 1:
                    raise StopAsyncIteration

            if not max_id:
                max_id = float('inf')
        else:
            offset_id = max(offset_id, max_id)
            if offset_id and min_id:
                if offset_id - min_id <= 1:
                    raise StopAsyncIteration

        if self.reverse:
            if offset_id:
                offset_id += 1
            elif not offset_date:
                # offset_id has priority over offset_date, so don't
                # set offset_id to 1 if we want to offset by date.
                offset_id = 1

        if from_user:
            from_user = await self.client.get_input_entity(from_user)
            self.from_id = await self.client.get_peer_id(from_user)
        else:
            self.from_id = None

        # `messages.searchGlobal` only works with text `search` or `filter` queries.
        # If we want to perform global a search with `from_user` we have to perform
        # a normal `messages.search`, *but* we can make the entity be `inputPeerEmpty`.
        if not self.entity and from_user:
            self.entity = types.InputPeerEmpty()

        if filter is None:
            filter = types.InputMessagesFilterEmpty()
        else:
            filter = filter() if isinstance(filter, type) else filter

        if not self.entity:
            self.request = functions.messages.SearchGlobalRequest(
                q=search or '',
                filter=filter,
                min_date=None,
                max_date=offset_date,
                offset_rate=0,
                offset_peer=types.InputPeerEmpty(),
                offset_id=offset_id,
                limit=1
            )
        elif scheduled:
            self.request = functions.messages.GetScheduledHistoryRequest(
                peer=entity,
                hash=0
            )
        elif reply_to is not None:
            self.request = functions.messages.GetRepliesRequest(
                peer=self.entity,
                msg_id=reply_to,
                offset_id=offset_id,
                offset_date=offset_date,
                add_offset=add_offset,
                limit=1,
                max_id=0,
                min_id=0,
                hash=0
            )
        elif search is not None or not isinstance(filter, types.InputMessagesFilterEmpty) or from_user:
            # Telegram completely ignores `from_id` in private chats
            ty = helpers._entity_type(self.entity)
            if ty == helpers._EntityType.USER:
                # Don't bother sending `from_user` (it's ignored anyway),
                # but keep `from_id` defined above to check it locally.
                from_user = None
            else:
                # Do send `from_user` to do the filtering server-side,
                # and set `from_id` to None to avoid checking it locally.
                self.from_id = None

            self.request = functions.messages.SearchRequest(
                peer=self.entity,
                q=search or '',
                filter=filter,
                min_date=None,
                max_date=offset_date,
                offset_id=offset_id,
                add_offset=add_offset,
                limit=0,  # Search actually returns 0 items if we ask it to
                max_id=0,
                min_id=0,
                hash=0,
                from_id=from_user
            )

            # Workaround issue #1124 until a better solution is found.
            # Telegram seemingly ignores `max_date` if `filter` (and
            # nothing else) is specified, so we have to rely on doing
            # a first request to offset from the ID instead.
            #
            # Even better, using `filter` and `from_id` seems to always
            # trigger `RPC_CALL_FAIL` which is "internal issues"...
            if not isinstance(filter, types.InputMessagesFilterEmpty) \
                    and offset_date and not search and not offset_id:
                async for m in self.client.iter_messages(
                        self.entity, 1, offset_date=offset_date):
                    self.request.offset_id = m.id + 1
        else:
            self.request = functions.messages.GetHistoryRequest(
                peer=self.entity,
                limit=1,
                offset_date=offset_date,
                offset_id=offset_id,
                min_id=0,
                max_id=0,
                add_offset=add_offset,
                hash=0
            )

        if self.limit <= 0:
            # No messages, but we still need to know the total message count
            result = await self.client(self.request)
            if isinstance(result, types.messages.MessagesNotModified):
                self.total = result.count
            else:
                self.total = getattr(result, 'count', len(result.messages))
            raise StopAsyncIteration

        if self.wait_time is None:
            self.wait_time = 1 if self.limit > 3000 else 0

        # When going in reverse we need an offset of `-limit`, but we
        # also want to respect what the user passed, so add them together.
        if self.reverse:
            self.request.add_offset -= _MAX_CHUNK_SIZE

        self.add_offset = add_offset
        self.max_id = max_id
        self.min_id = min_id
        self.last_id = 0 if self.reverse else float('inf')

    async def _load_next_chunk(self):
        self.request.limit = min(self.left, _MAX_CHUNK_SIZE)
        if self.reverse and self.request.limit != _MAX_CHUNK_SIZE:
            # Remember that we need -limit when going in reverse
            self.request.add_offset = self.add_offset - self.request.limit

        r = await self.client(self.request)
        self.total = getattr(r, 'count', len(r.messages))

        entities = {utils.get_peer_id(x): x
                    for x in itertools.chain(r.users, r.chats)}

        messages = reversed(r.messages) if self.reverse else r.messages
        for message in messages:
            if (isinstance(message, types.MessageEmpty)
                    or self.from_id and message.sender_id != self.from_id):
                continue

            if not self._message_in_range(message):
                return True

            # There has been reports that on bad connections this method
            # was returning duplicated IDs sometimes. Using ``last_id``
            # is an attempt to avoid these duplicates, since the message
            # IDs are returned in descending order (or asc if reverse).
            self.last_id = message.id
            message._finish_init(self.client, entities, self.entity)
            self.buffer.append(message)

        # Not a slice (using offset would return the same, with e.g. SearchGlobal).
        if isinstance(r, types.messages.Messages):
            return True

        # Some channels are "buggy" and may return less messages than
        # requested (apparently, the messages excluded are, for example,
        # "not displayable due to local laws").
        #
        # This means it's not safe to rely on `len(r.messages) < req.limit` as
        # the stop condition. Unfortunately more requests must be made.
        #
        # However we can still check if the highest ID is equal to or lower
        # than the limit, in which case there won't be any more messages
        # because the lowest message ID is 1.
        #
        # We also assume the API will always return, at least, one message if
        # there is more to fetch.
        if not r.messages or r.messages[0].id <= self.request.limit:
            return True

        # Get the last message that's not empty (in some rare cases
        # it can happen that the last message is :tl:`MessageEmpty`)
        if self.buffer:
            self._update_offset(self.buffer[-1], r)
        else:
            # There are some cases where all the messages we get start
            # being empty. This can happen on migrated mega-groups if
            # the history was cleared, and we're using search. Telegram
            # acts incredibly weird sometimes. Messages are returned but
            # only "empty", not their contents. If this is the case we
            # should just give up since there won't be any new Message.
            return True

    def _message_in_range(self, message):
        """
        Determine whether the given message is in the range or
        it should be ignored (and avoid loading more chunks).
        """
        # No entity means message IDs between chats may vary
        if self.entity:
            if self.reverse:
                if message.id <= self.last_id or message.id >= self.max_id:
                    return False
            else:
                if message.id >= self.last_id or message.id <= self.min_id:
                    return False

        return True

    def _update_offset(self, last_message, response):
        """
        After making the request, update its offset with the last message.
        """
        self.request.offset_id = last_message.id
        if self.reverse:
            # We want to skip the one we already have
            self.request.offset_id += 1

        if isinstance(self.request, functions.messages.SearchRequest):
            # Unlike getHistory and searchGlobal that use *offset* date,
            # this is *max* date. This means that doing a search in reverse
            # will break it. Since it's not really needed once we're going
            # (only for the first request), it's safe to just clear it off.
            self.request.max_date = None
        else:
            # getHistory, searchGlobal and getReplies call it offset_date
            self.request.offset_date = last_message.date

        if isinstance(self.request, functions.messages.SearchGlobalRequest):
            if last_message.input_chat:
                self.request.offset_peer = last_message.input_chat
            else:
                self.request.offset_peer = types.InputPeerEmpty()

            self.request.offset_rate = getattr(response, 'next_rate', 0)


class _IDsIter(RequestIter):
    async def _init(self, entity, ids):
        self.total = len(ids)
        self._ids = list(reversed(ids)) if self.reverse else ids
        self._offset = 0
        self._entity = (await self.client.get_input_entity(entity)) if entity else None
        self._ty = helpers._entity_type(self._entity) if self._entity else None

        # 30s flood wait every 300 messages (3 requests of 100 each, 30 of 10, etc.)
        if self.wait_time is None:
            self.wait_time = 10 if self.limit > 300 else 0

    async def _load_next_chunk(self):
        ids = self._ids[self._offset:self._offset + _MAX_CHUNK_SIZE]
        if not ids:
            raise StopAsyncIteration

        self._offset += _MAX_CHUNK_SIZE

        from_id = None  # By default, no need to validate from_id
        if self._ty == helpers._EntityType.CHANNEL:
            try:
                r = await self.client(
                    functions.channels.GetMessagesRequest(self._entity, ids))
            except errors.MessageIdsEmptyError:
                # All IDs were invalid, use a dummy result
                r = types.messages.MessagesNotModified(len(ids))
        else:
            r = await self.client(functions.messages.GetMessagesRequest(ids))
            if self._entity:
                from_id = await self.client._get_peer(self._entity)

        if isinstance(r, types.messages.MessagesNotModified):
            self.buffer.extend(None for _ in ids)
            return

        entities = {utils.get_peer_id(x): x
                    for x in itertools.chain(r.users, r.chats)}

        # Telegram seems to return the messages in the order in which
        # we asked them for, so we don't need to check it ourselves,
        # unless some messages were invalid in which case Telegram
        # may decide to not send them at all.
        #
        # The passed message IDs may not belong to the desired entity
        # since the user can enter arbitrary numbers which can belong to
        # arbitrary chats. Validate these unless ``from_id is None``.
        for message in r.messages:
            if isinstance(message, types.MessageEmpty) or (
                    from_id and message.peer_id != from_id):
                self.buffer.append(None)
            else:
                message._finish_init(self.client, entities, self._entity)
                self.buffer.append(message)


class MessageMethods:

    # region Public methods

    # region Message retrieval

    def iter_messages(
            self: 'TelegramClient',
            entity: 'hints.EntityLike',
            limit: float = None,
            *,
            offset_date: 'hints.DateLike' = None,
            offset_id: int = 0,
            max_id: int = 0,
            min_id: int = 0,
            add_offset: int = 0,
            search: str = None,
            filter: 'typing.Union[types.TypeMessagesFilter, typing.Type[types.TypeMessagesFilter]]' = None,
            from_user: 'hints.EntityLike' = None,
            wait_time: float = None,
            ids: 'typing.Union[int, typing.Sequence[int]]' = None,
            reverse: bool = False,
            reply_to: int = None,
            scheduled: bool = False
    ) -> 'typing.Union[_MessagesIter, _IDsIter]':
        """
        Iterator over the messages for the given chat.

        The default order is from newest to oldest, but this
        behaviour can be changed with the `reverse` parameter.

        If either `search`, `filter` or `from_user` are provided,
        :tl:`messages.Search` will be used instead of :tl:`messages.getHistory`.

        .. note::

            Telegram's flood wait limit for :tl:`GetHistoryRequest` seems to
            be around 30 seconds per 10 requests, therefore a sleep of 1
            second is the default for this limit (or above).

        Arguments
            entity (`entity`):
                The entity from whom to retrieve the message history.

                It may be `None` to perform a global search, or
                to get messages by their ID from no particular chat.
                Note that some of the offsets will not work if this
                is the case.

                Note that if you want to perform a global search,
                you **must** set a non-empty `search` string, a `filter`.
                or `from_user`.

            limit (`int` | `None`, optional):
                Number of messages to be retrieved. Due to limitations with
                the API retrieving more than 3000 messages will take longer
                than half a minute (or even more based on previous calls).

                The limit may also be `None`, which would eventually return
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
                Only messages from this entity will be returned.

            wait_time (`int`):
                Wait time (in seconds) between different
                :tl:`GetHistoryRequest`. Use this parameter to avoid hitting
                the ``FloodWaitError`` as needed. If left to `None`, it will
                default to 1 second only if the limit is higher than 3000.

                If the ``ids`` parameter is used, this time will default
                to 10 seconds only if the amount of IDs is higher than 300.

            ids (`int`, `list`):
                A single integer ID (or several IDs) for the message that
                should be returned. This parameter takes precedence over
                the rest (which will be ignored if this is set). This can
                for instance be used to get the message with ID 123 from
                a channel. Note that if the message doesn't exist, `None`
                will appear in its place, so that zipping the list of IDs
                with the messages can match one-to-one.

                .. note::

                    At the time of writing, Telegram will **not** return
                    :tl:`MessageEmpty` for :tl:`InputMessageReplyTo` IDs that
                    failed (i.e. the message is not replying to any, or is
                    replying to a deleted message). This means that it is
                    **not** possible to match messages one-by-one, so be
                    careful if you use non-integers in this parameter.

            reverse (`bool`, optional):
                If set to `True`, the messages will be returned in reverse
                order (from oldest to newest, instead of the default newest
                to oldest). This also means that the meaning of `offset_id`
                and `offset_date` parameters is reversed, although they will
                still be exclusive. `min_id` becomes equivalent to `offset_id`
                instead of being `max_id` as well since messages are returned
                in ascending order.

                You cannot use this if both `entity` and `ids` are `None`.

            reply_to (`int`, optional):
                If set to a message ID, the messages that reply to this ID
                will be returned. This feature is also known as comments in
                posts of broadcast channels, or viewing threads in groups.

                This feature can only be used in broadcast channels and their
                linked megagroups. Using it in a chat or private conversation
                will result in ``telethon.errors.PeerIdInvalidError`` to occur.

                When using this parameter, the ``filter`` and ``search``
                parameters have no effect, since Telegram's API doesn't
                support searching messages in replies.

                .. note::

                    This feature is used to get replies to a message in the
                    *discussion* group. If the same broadcast channel sends
                    a message and replies to it itself, that reply will not
                    be included in the results.

            scheduled (`bool`, optional):
                If set to `True`, messages which are scheduled will be returned.
                All other parameter will be ignored for this, except `entity`.

        Yields
            Instances of `Message <telethon.tl.custom.message.Message>`.

        Example
            .. code-block:: python

                # From most-recent to oldest
                async for message in client.iter_messages(chat):
                    print(message.id, message.text)

                # From oldest to most-recent
                async for message in client.iter_messages(chat, reverse=True):
                    print(message.id, message.text)

                # Filter by sender
                async for message in client.iter_messages(chat, from_user='me'):
                    print(message.text)

                # Server-side search with fuzzy text
                async for message in client.iter_messages(chat, search='hello'):
                    print(message.id)

                # Filter by message type:
                from telethon.tl.types import InputMessagesFilterPhotos
                async for message in client.iter_messages(chat, filter=InputMessagesFilterPhotos):
                    print(message.photo)

                # Getting comments from a post in a channel:
                async for message in client.iter_messages(channel, reply_to=123):
                    print(message.chat.title, message.text)
        """
        if ids is not None:
            if not utils.is_list_like(ids):
                ids = [ids]

            return _IDsIter(
                client=self,
                reverse=reverse,
                wait_time=wait_time,
                limit=len(ids),
                entity=entity,
                ids=ids
            )

        return _MessagesIter(
            client=self,
            reverse=reverse,
            wait_time=wait_time,
            limit=limit,
            entity=entity,
            offset_id=offset_id,
            min_id=min_id,
            max_id=max_id,
            from_user=from_user,
            offset_date=offset_date,
            add_offset=add_offset,
            filter=filter,
            search=search,
            reply_to=reply_to,
            scheduled=scheduled
        )

    async def get_messages(
            self: 'TelegramClient', *args, **kwargs
    ) -> typing.Union['hints.TotalList', typing.Optional['types.Message']]:
        """
        Same as `iter_messages()`, but returns a
        `TotalList <telethon.helpers.TotalList>` instead.

        If the `limit` is not set, it will be 1 by default unless both
        `min_id` **and** `max_id` are set (as *named* arguments), in
        which case the entire range will be returned.

        This is so because any integer limit would be rather arbitrary and
        it's common to only want to fetch one message, but if a range is
        specified it makes sense that it should return the entirety of it.

        If `ids` is present in the *named* arguments and is not a list,
        a single `Message <telethon.tl.custom.message.Message>` will be
        returned for convenience instead of a list.

        Example
            .. code-block:: python

                # Get 0 photos and print the total to show how many photos there are
                from telethon.tl.types import InputMessagesFilterPhotos
                photos = await client.get_messages(chat, 0, filter=InputMessagesFilterPhotos)
                print(photos.total)

                # Get all the photos
                photos = await client.get_messages(chat, None, filter=InputMessagesFilterPhotos)

                # Get messages by ID:
                message_1337 = await client.get_messages(chat, ids=1337)
        """
        if len(args) == 1 and 'limit' not in kwargs:
            if 'min_id' in kwargs and 'max_id' in kwargs:
                kwargs['limit'] = None
            else:
                kwargs['limit'] = 1

        it = self.iter_messages(*args, **kwargs)

        ids = kwargs.get('ids')
        if ids and not utils.is_list_like(ids):
            async for message in it:
                return message
            else:
                # Iterator exhausted = empty, to handle InputMessageReplyTo
                return None

        return await it.collect()

    get_messages.__signature__ = inspect.signature(iter_messages)

    # endregion

    # region Message sending/editing/deleting

    async def _get_comment_data(
            self: 'TelegramClient',
            entity: 'hints.EntityLike',
            message: 'typing.Union[int, types.Message]'
    ):
        r = await self(functions.messages.GetDiscussionMessageRequest(
            peer=entity,
            msg_id=utils.get_message_id(message)
        ))
        m = min(r.messages, key=lambda msg: msg.id)
        chat = next(c for c in r.chats if c.id == m.peer_id.channel_id)
        return utils.get_input_peer(chat), m.id

    async def send_message(
            self: 'TelegramClient',
            entity: 'hints.EntityLike',
            message: 'hints.MessageLike' = '',
            *,
            reply_to: 'typing.Union[int, types.Message]' = None,
            attributes: 'typing.Sequence[types.TypeDocumentAttribute]' = None,
            parse_mode: typing.Optional[str] = (),
            formatting_entities: typing.Optional[typing.List[types.TypeMessageEntity]] = None,
            link_preview: bool = True,
            file: 'typing.Union[hints.FileLike, typing.Sequence[hints.FileLike]]' = None,
            thumb: 'hints.FileLike' = None,
            force_document: bool = False,
            clear_draft: bool = False,
            buttons: typing.Optional['hints.MarkupLike'] = None,
            silent: bool = None,
            background: bool = None,
            supports_streaming: bool = False,
            schedule: 'hints.DateLike' = None,
            comment_to: 'typing.Union[int, types.Message]' = None,
            nosound_video: bool = None,
    ) -> 'types.Message':
        """
        Sends a message to the specified user, chat or channel.

        The default parse mode is the same as the official applications
        (a custom flavour of markdown). ``**bold**, `code` or __italic__``
        are available. In addition you can send ``[links](https://example.com)``
        and ``[mentions](@username)`` (or using IDs like in the Bot API:
        ``[mention](tg://user?id=123456789)``) and ``pre`` blocks with three
        backticks.

        Sending a ``/start`` command with a parameter (like ``?start=data``)
        is also done through this method. Simply send ``'/start data'`` to
        the bot.

        See also `Message.respond() <telethon.tl.custom.message.Message.respond>`
        and `Message.reply() <telethon.tl.custom.message.Message.reply>`.

        Arguments
            entity (`entity`):
                To who will it be sent.

            message (`str` | `Message <telethon.tl.custom.message.Message>`):
                The message to be sent, or another message object to resend.

                The maximum length for a message is 35,000 bytes or 4,096
                characters. Longer messages will not be sliced automatically,
                and you should slice them manually if the text to send is
                longer than said length.

            reply_to (`int` | `Message <telethon.tl.custom.message.Message>`, optional):
                Whether to reply to a message or not. If an integer is provided,
                it should be the ID of the message that it should reply to.

            attributes (`list`, optional):
                Optional attributes that override the inferred ones, like
                :tl:`DocumentAttributeFilename` and so on.

            parse_mode (`object`, optional):
                See the `TelegramClient.parse_mode
                <telethon.client.messageparse.MessageParseMethods.parse_mode>`
                property for allowed values. Markdown parsing will be used by
                default.

            formatting_entities (`list`, optional):
                A list of message formatting entities. When provided, the ``parse_mode`` is ignored.

            link_preview (`bool`, optional):
                Should the link preview be shown?

            file (`file`, optional):
                Sends a message with a file attached (e.g. a photo,
                video, audio or document). The ``message`` may be empty.

            thumb (`str` | `bytes` | `file`, optional):
                Optional JPEG thumbnail (for documents). **Telegram will
                ignore this parameter** unless you pass a ``.jpg`` file!
                The file must also be small in dimensions and in disk size.
                Successful thumbnails were files below 20kB and 320x320px.
                Width/height and dimensions/size ratios may be important.
                For Telegram to accept a thumbnail, you must provide the
                dimensions of the underlying media through ``attributes=``
                with :tl:`DocumentAttributesVideo` or by installing the
                optional ``hachoir`` dependency.

            force_document (`bool`, optional):
                Whether to send the given file as a document or not.

            clear_draft (`bool`, optional):
                Whether the existing draft should be cleared or not.

            buttons (`list`, `custom.Button <telethon.tl.custom.button.Button>`, :tl:`KeyboardButton`):
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
                channel or not. Defaults to `False`, which means it will
                notify them. Set it to `True` to alter this behaviour.

            background (`bool`, optional):
                Whether the message should be send in background.

            supports_streaming (`bool`, optional):
                Whether the sent video supports streaming or not. Note that
                Telegram only recognizes as streamable some formats like MP4,
                and others like AVI or MKV will not work. You should convert
                these to MP4 before sending if you want them to be streamable.
                Unsupported formats will result in ``VideoContentTypeError``.

            schedule (`hints.DateLike`, optional):
                If set, the message won't send immediately, and instead
                it will be scheduled to be automatically sent at a later
                time.

            comment_to (`int` | `Message <telethon.tl.custom.message.Message>`, optional):
                Similar to ``reply_to``, but replies in the linked group of a
                broadcast channel instead (effectively leaving a "comment to"
                the specified message).

                This parameter takes precedence over ``reply_to``. If there is
                no linked chat, `telethon.errors.sgIdInvalidError` is raised.

            nosound_video (`bool`, optional):
                Only applicable when sending a video file without an audio
                track. If set to ``True``, the video will be displayed in
                Telegram as a video. If set to ``False``, Telegram will attempt
                to display the video as an animated gif. (It may still display
                as a video due to other factors.) The value is ignored if set
                on non-video files. This is set to ``True`` for albums, as gifs
                cannot be sent in albums.

        Returns
            The sent `custom.Message <telethon.tl.custom.message.Message>`.

        Example
            .. code-block:: python

                # Markdown is the default
                await client.send_message('me', 'Hello **world**!')

                # Default to another parse mode
                client.parse_mode = 'html'

                await client.send_message('me', 'Some <b>bold</b> and <i>italic</i> text')
                await client.send_message('me', 'An <a href="https://example.com">URL</a>')
                # code and pre tags also work, but those break the documentation :)
                await client.send_message('me', '<a href="tg://user?id=me">Mentions</a>')

                # Explicit parse mode
                # No parse mode by default
                client.parse_mode = None

                # ...but here I want markdown
                await client.send_message('me', 'Hello, **world**!', parse_mode='md')

                # ...and here I need HTML
                await client.send_message('me', 'Hello, <i>world</i>!', parse_mode='html')

                # If you logged in as a bot account, you can send buttons
                from telethon import events, Button

                @client.on(events.CallbackQuery)
                async def callback(event):
                    await event.edit('Thank you for clicking {}!'.format(event.data))

                # Single inline button
                await client.send_message(chat, 'A single button, with "clk1" as data',
                                          buttons=Button.inline('Click me', b'clk1'))

                # Matrix of inline buttons
                await client.send_message(chat, 'Pick one from this grid', buttons=[
                    [Button.inline('Left'), Button.inline('Right')],
                    [Button.url('Check this site!', 'https://example.com')]
                ])

                # Reply keyboard
                await client.send_message(chat, 'Welcome', buttons=[
                    Button.text('Thanks!', resize=True, single_use=True),
                    Button.request_phone('Send phone'),
                    Button.request_location('Send location')
                ])

                # Forcing replies or clearing buttons.
                await client.send_message(chat, 'Reply to me', buttons=Button.force_reply())
                await client.send_message(chat, 'Bye Keyboard!', buttons=Button.clear())

                # Scheduling a message to be sent after 5 minutes
                from datetime import timedelta
                await client.send_message(chat, 'Hi, future!', schedule=timedelta(minutes=5))
        """
        if file is not None:
            return await self.send_file(
                entity, file, caption=message, reply_to=reply_to,
                attributes=attributes, parse_mode=parse_mode,
                force_document=force_document, thumb=thumb,
                buttons=buttons, clear_draft=clear_draft, silent=silent,
                schedule=schedule, supports_streaming=supports_streaming,
                formatting_entities=formatting_entities,
                comment_to=comment_to, background=background,
                nosound_video=nosound_video,
            )

        entity = await self.get_input_entity(entity)
        if comment_to is not None:
            entity, reply_to = await self._get_comment_data(entity, comment_to)
        else:
            reply_to = utils.get_message_id(reply_to)

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
                    background=background,
                    reply_to=reply_to,
                    buttons=markup,
                    formatting_entities=message.entities,
                    parse_mode=None,  # explicitly disable parse_mode to force using even empty formatting_entities
                    schedule=schedule
                )

            request = functions.messages.SendMessageRequest(
                peer=entity,
                message=message.message or '',
                silent=silent,
                background=background,
                reply_to=None if reply_to is None else types.InputReplyToMessage(reply_to),
                reply_markup=markup,
                entities=message.entities,
                clear_draft=clear_draft,
                no_webpage=not isinstance(
                    message.media, types.MessageMediaWebPage),
                schedule_date=schedule
            )
            message = message.message
        else:
            if formatting_entities is None:
                message, formatting_entities = await self._parse_message_text(message, parse_mode)
            if not message:
                raise ValueError(
                    'The message cannot be empty unless a file is provided'
                )

            request = functions.messages.SendMessageRequest(
                peer=entity,
                message=message,
                entities=formatting_entities,
                no_webpage=not link_preview,
                reply_to=None if reply_to is None else types.InputReplyToMessage(reply_to),
                clear_draft=clear_draft,
                silent=silent,
                background=background,
                reply_markup=self.build_reply_markup(buttons),
                schedule_date=schedule
            )

        result = await self(request)
        if isinstance(result, types.UpdateShortSentMessage):
            message = types.Message(
                id=result.id,
                peer_id=await self._get_peer(entity),
                message=message,
                date=result.date,
                out=result.out,
                media=result.media,
                entities=result.entities,
                reply_markup=request.reply_markup,
                ttl_period=result.ttl_period,
                reply_to=request.reply_to
            )
            message._finish_init(self, {}, entity)
            return message

        return self._get_response_message(request, result, entity)

    async def forward_messages(
            self: 'TelegramClient',
            entity: 'hints.EntityLike',
            messages: 'typing.Union[hints.MessageIDLike, typing.Sequence[hints.MessageIDLike]]',
            from_peer: 'hints.EntityLike' = None,
            *,
            background: bool = None,
            with_my_score: bool = None,
            silent: bool = None,
            as_album: bool = None,
            schedule: 'hints.DateLike' = None,
            drop_author: bool = None,
    ) -> 'typing.Sequence[types.Message]':
        """
        Forwards the given messages to the specified entity.

        If you want to "forward" a message without the forward header
        (the "forwarded from" text), you should use `send_message` with
        the original message instead. This will send a copy of it.

        See also `Message.forward_to() <telethon.tl.custom.message.Message.forward_to>`.

        Arguments
            entity (`entity`):
                To which entity the message(s) will be forwarded.

            messages (`list` | `int` | `Message <telethon.tl.custom.message.Message>`):
                The message(s) to forward, or their integer IDs.

            from_peer (`entity`):
                If the given messages are integer IDs and not instances
                of the ``Message`` class, this *must* be specified in
                order for the forward to work. This parameter indicates
                the entity from which the messages should be forwarded.

            silent (`bool`, optional):
                Whether the message should notify people with sound or not.
                Defaults to `False` (send with a notification sound unless
                the person has the chat muted). Set it to `True` to alter
                this behaviour.

            background (`bool`, optional):
                Whether the message should be forwarded in background.

            with_my_score (`bool`, optional):
                Whether forwarded should contain your game score.

            as_album (`bool`, optional):
                This flag no longer has any effect.

            schedule (`hints.DateLike`, optional):
                If set, the message(s) won't forward immediately, and
                instead they will be scheduled to be automatically sent
                at a later time.

        Returns
            The list of forwarded `Message <telethon.tl.custom.message.Message>`,
            or a single one if a list wasn't provided as input.

            Note that if all messages are invalid (i.e. deleted) the call
            will fail with ``MessageIdInvalidError``. If only some are
            invalid, the list will have `None` instead of those messages.

        Example
            .. code-block:: python

                # a single one
                await client.forward_messages(chat, message)
                # or
                await client.forward_messages(chat, message_id, from_chat)
                # or
                await message.forward_to(chat)

                # multiple
                await client.forward_messages(chat, messages)
                # or
                await client.forward_messages(chat, message_ids, from_chat)

                # Forwarding as a copy
                await client.send_message(chat, message)
        """
        if as_album is not None:
            warnings.warn('the as_album argument is deprecated and no longer has any effect')

        single = not utils.is_list_like(messages)
        if single:
            messages = (messages,)

        entity = await self.get_input_entity(entity)

        if from_peer:
            from_peer = await self.get_input_entity(from_peer)
            from_peer_id = await self.get_peer_id(from_peer)
        else:
            from_peer_id = None

        def get_key(m):
            if isinstance(m, int):
                if from_peer_id is not None:
                    return from_peer_id

                raise ValueError('from_peer must be given if integer IDs are used')
            elif isinstance(m, types.Message):
                return m.chat_id
            else:
                raise TypeError('Cannot forward messages of type {}'.format(type(m)))

        sent = []
        for _chat_id, chunk in itertools.groupby(messages, key=get_key):
            chunk = list(chunk)
            if isinstance(chunk[0], int):
                chat = from_peer
            else:
                chat = from_peer or await self.get_input_entity(chunk[0].peer_id)
                chunk = [m.id for m in chunk]

            req = functions.messages.ForwardMessagesRequest(
                from_peer=chat,
                id=chunk,
                to_peer=entity,
                silent=silent,
                background=background,
                with_my_score=with_my_score,
                schedule_date=schedule,
                drop_author=drop_author
            )
            result = await self(req)
            sent.extend(self._get_response_message(req, result, entity))

        return sent[0] if single else sent

    async def edit_message(
            self: 'TelegramClient',
            entity: 'typing.Union[hints.EntityLike, types.Message]',
            message: 'hints.MessageLike' = None,
            text: str = None,
            *,
            parse_mode: str = (),
            attributes: 'typing.Sequence[types.TypeDocumentAttribute]' = None,
            formatting_entities: typing.Optional[typing.List[types.TypeMessageEntity]] = None,
            link_preview: bool = True,
            file: 'hints.FileLike' = None,
            thumb: 'hints.FileLike' = None,
            force_document: bool = False,
            buttons: typing.Optional['hints.MarkupLike'] = None,
            supports_streaming: bool = False,
            schedule: 'hints.DateLike' = None
    ) -> 'types.Message':
        """
        Edits the given message to change its text or media.

        See also `Message.edit() <telethon.tl.custom.message.Message.edit>`.

        Arguments
            entity (`entity` | `Message <telethon.tl.custom.message.Message>`):
                From which chat to edit the message. This can also be
                the message to be edited, and the entity will be inferred
                from it, so the next parameter will be assumed to be the
                message text.

                You may also pass a :tl:`InputBotInlineMessageID` or :tl:`InputBotInlineMessageID64`,
                which is the only way to edit messages that were sent
                after the user selects an inline query result.

            message (`int` | `Message <telethon.tl.custom.message.Message>` | `str`):
                The ID of the message (or `Message
                <telethon.tl.custom.message.Message>` itself) to be edited.
                If the `entity` was a `Message
                <telethon.tl.custom.message.Message>`, then this message
                will be treated as the new text.

            text (`str`, optional):
                The new text of the message. Does nothing if the `entity`
                was a `Message <telethon.tl.custom.message.Message>`.

            parse_mode (`object`, optional):
                See the `TelegramClient.parse_mode
                <telethon.client.messageparse.MessageParseMethods.parse_mode>`
                property for allowed values. Markdown parsing will be used by
                default.

            attributes (`list`, optional):
                Optional attributes that override the inferred ones, like
                :tl:`DocumentAttributeFilename` and so on.

            formatting_entities (`list`, optional):
                A list of message formatting entities. When provided, the ``parse_mode`` is ignored.

            link_preview (`bool`, optional):
                Should the link preview be shown?

            file (`str` | `bytes` | `file` | `media`, optional):
                The file object that should replace the existing media
                in the message.

            thumb (`str` | `bytes` | `file`, optional):
                Optional JPEG thumbnail (for documents). **Telegram will
                ignore this parameter** unless you pass a ``.jpg`` file!
                The file must also be small in dimensions and in disk size.
                Successful thumbnails were files below 20kB and 320x320px.
                Width/height and dimensions/size ratios may be important.
                For Telegram to accept a thumbnail, you must provide the
                dimensions of the underlying media through ``attributes=``
                with :tl:`DocumentAttributesVideo` or by installing the
                optional ``hachoir`` dependency.

            force_document (`bool`, optional):
                Whether to send the given file as a document or not.

            buttons (`list`, `custom.Button <telethon.tl.custom.button.Button>`, :tl:`KeyboardButton`):
                The matrix (list of lists), row list or button to be shown
                after sending the message. This parameter will only work if
                you have signed in as a bot. You can also pass your own
                :tl:`ReplyMarkup` here.

            supports_streaming (`bool`, optional):
                Whether the sent video supports streaming or not. Note that
                Telegram only recognizes as streamable some formats like MP4,
                and others like AVI or MKV will not work. You should convert
                these to MP4 before sending if you want them to be streamable.
                Unsupported formats will result in ``VideoContentTypeError``.

            schedule (`hints.DateLike`, optional):
                If set, the message won't be edited immediately, and instead
                it will be scheduled to be automatically edited at a later
                time.

                Note that this parameter will have no effect if you are
                trying to edit a message that was sent via inline bots.

        Returns
            The edited `Message <telethon.tl.custom.message.Message>`,
            unless `entity` was a :tl:`InputBotInlineMessageID` or :tl:`InputBotInlineMessageID64` in which
            case this method returns a boolean.

        Raises
            ``MessageAuthorRequiredError`` if you're not the author of the
            message but tried editing it anyway.

            ``MessageNotModifiedError`` if the contents of the message were
            not modified at all.

            ``MessageIdInvalidError`` if the ID of the message is invalid
            (the ID itself may be correct, but the message with that ID
            cannot be edited). For example, when trying to edit messages
            with a reply markup (or clear markup) this error will be raised.

        Example
            .. code-block:: python

                message = await client.send_message(chat, 'hello')

                await client.edit_message(chat, message, 'hello!')
                # or
                await client.edit_message(chat, message.id, 'hello!!')
                # or
                await client.edit_message(message, 'hello!!!')
        """
        if isinstance(entity, (types.InputBotInlineMessageID, types.InputBotInlineMessageID64)):
            text = text or message
            message = entity
        elif isinstance(entity, types.Message):
            text = message  # Shift the parameters to the right
            message = entity
            entity = entity.peer_id

        if formatting_entities is None:
            text, formatting_entities = await self._parse_message_text(text, parse_mode)
        file_handle, media, image = await self._file_to_media(file,
                supports_streaming=supports_streaming,
                thumb=thumb,
                attributes=attributes,
                force_document=force_document)

        if isinstance(entity, (types.InputBotInlineMessageID, types.InputBotInlineMessageID64)):
            request = functions.messages.EditInlineBotMessageRequest(
                id=entity,
                message=text,
                no_webpage=not link_preview,
                entities=formatting_entities,
                media=media,
                reply_markup=self.build_reply_markup(buttons)
            )
            # Invoke `messages.editInlineBotMessage` from the right datacenter.
            # Otherwise, Telegram will error with `MESSAGE_ID_INVALID` and do nothing.
            exported = self.session.dc_id != entity.dc_id
            if exported:
                try:
                    sender = await self._borrow_exported_sender(entity.dc_id)
                    return await self._call(sender, request)
                finally:
                    await self._return_exported_sender(sender)
            else:
                return await self(request)

        entity = await self.get_input_entity(entity)
        request = functions.messages.EditMessageRequest(
            peer=entity,
            id=utils.get_message_id(message),
            message=text,
            no_webpage=not link_preview,
            entities=formatting_entities,
            media=media,
            reply_markup=self.build_reply_markup(buttons),
            schedule_date=schedule
        )
        msg = self._get_response_message(request, await self(request), entity)
        return msg

    async def delete_messages(
            self: 'TelegramClient',
            entity: 'hints.EntityLike',
            message_ids: 'typing.Union[hints.MessageIDLike, typing.Sequence[hints.MessageIDLike]]',
            *,
            revoke: bool = True) -> 'typing.Sequence[types.messages.AffectedMessages]':
        """
        Deletes the given messages, optionally "for everyone".

        See also `Message.delete() <telethon.tl.custom.message.Message.delete>`.

        .. warning::

            This method does **not** validate that the message IDs belong
            to the chat that you passed! It's possible for the method to
            delete messages from different private chats and small group
            chats at once, so make sure to pass the right IDs.

        Arguments
            entity (`entity`):
                From who the message will be deleted. This can actually
                be `None` for normal chats, but **must** be present
                for channels and megagroups.

            message_ids (`list` | `int` | `Message <telethon.tl.custom.message.Message>`):
                The IDs (or ID) or messages to be deleted.

            revoke (`bool`, optional):
                Whether the message should be deleted for everyone or not.
                By default it has the opposite behaviour of official clients,
                and it will delete the message for everyone.

                `Since 24 March 2019
                <https://telegram.org/blog/unsend-privacy-emoji>`_, you can
                also revoke messages of any age (i.e. messages sent long in
                the past) the *other* person sent in private conversations
                (and of course your messages too).

                Disabling this has no effect on channels or megagroups,
                since it will unconditionally delete the message for everyone.

        Returns
            A list of :tl:`AffectedMessages`, each item being the result
            for the delete calls of the messages in chunks of 100 each.

        Example
            .. code-block:: python

                await client.delete_messages(chat, messages)
        """
        if not utils.is_list_like(message_ids):
            message_ids = (message_ids,)

        message_ids = (
            m.id if isinstance(m, (
                types.Message, types.MessageService, types.MessageEmpty))
            else int(m) for m in message_ids
        )

        if entity:
            entity = await self.get_input_entity(entity)
            ty = helpers._entity_type(entity)
        else:
            # no entity (None), set a value that's not a channel for private delete
            ty = helpers._EntityType.USER

        if ty == helpers._EntityType.CHANNEL:
            return await self([functions.channels.DeleteMessagesRequest(
                         entity, list(c)) for c in utils.chunks(message_ids)])
        else:
            return await self([functions.messages.DeleteMessagesRequest(
                         list(c), revoke) for c in utils.chunks(message_ids)])

    # endregion

    # region Miscellaneous

    async def send_read_acknowledge(
            self: 'TelegramClient',
            entity: 'hints.EntityLike',
            message: 'typing.Union[hints.MessageIDLike, typing.Sequence[hints.MessageIDLike]]' = None,
            *,
            max_id: int = None,
            clear_mentions: bool = False,
            clear_reactions: bool = False) -> bool:
        """
        Marks messages as read and optionally clears mentions.

        This effectively marks a message as read (or more than one) in the
        given conversation.

        If neither message nor maximum ID are provided, all messages will be
        marked as read by assuming that ``max_id = 0``.

        If a message or maximum ID is provided, all the messages up to and
        including such ID will be marked as read (for all messages whose ID
        ≤ max_id).

        See also `Message.mark_read() <telethon.tl.custom.message.Message.mark_read>`.

        Arguments
            entity (`entity`):
                The chat where these messages are located.

            message (`list` | `Message <telethon.tl.custom.message.Message>`):
                Either a list of messages or a single message.

            max_id (`int`):
                Until which message should the read acknowledge be sent for.
                This has priority over the ``message`` parameter.

            clear_mentions (`bool`):
                Whether the mention badge should be cleared (so that
                there are no more mentions) or not for the given entity.

                If no message is provided, this will be the only action
                taken.

            clear_reactions (`bool`):
                Whether the reactions badge should be cleared (so that
                there are no more reaction notifications) or not for the given entity.

                If no message is provided, this will be the only action
                taken.

        Example
            .. code-block:: python

                # using a Message object
                await client.send_read_acknowledge(chat, message)
                # ...or using the int ID of a Message
                await client.send_read_acknowledge(chat, message_id)
                # ...or passing a list of messages to mark as read
                await client.send_read_acknowledge(chat, messages)
        """
        if max_id is None:
            if not message:
                max_id = 0
            else:
                if utils.is_list_like(message):
                    max_id = max(msg.id for msg in message)
                else:
                    max_id = message.id

        entity = await self.get_input_entity(entity)
        if clear_mentions:
            await self(functions.messages.ReadMentionsRequest(entity))
            if max_id is None and not clear_reactions:
                return True
        if clear_reactions:
            await self(functions.messages.ReadReactionsRequest(entity))
            if max_id is None:
                return True

        if max_id is not None:
            if helpers._entity_type(entity) == helpers._EntityType.CHANNEL:
                return await self(functions.channels.ReadHistoryRequest(
                    utils.get_input_channel(entity), max_id=max_id))
            else:
                return await self(functions.messages.ReadHistoryRequest(
                    entity, max_id=max_id))

        return False

    async def pin_message(
            self: 'TelegramClient',
            entity: 'hints.EntityLike',
            message: 'typing.Optional[hints.MessageIDLike]',
            *,
            notify: bool = False,
            pm_oneside: bool = False
    ):
        """
        Pins a message in a chat.

        The default behaviour is to *not* notify members, unlike the
        official applications.

        See also `Message.pin() <telethon.tl.custom.message.Message.pin>`.

        Arguments
            entity (`entity`):
                The chat where the message should be pinned.

            message (`int` | `Message <telethon.tl.custom.message.Message>`):
                The message or the message ID to pin. If it's
                `None`, all messages will be unpinned instead.

            notify (`bool`, optional):
                Whether the pin should notify people or not.

            pm_oneside (`bool`, optional):
                Whether the message should be pinned for everyone or not.
                By default it has the opposite behaviour of official clients,
                and it will pin the message for both sides, in private chats.

        Example
            .. code-block:: python

                # Send and pin a message to annoy everyone
                message = await client.send_message(chat, 'Pinotifying is fun!')
                await client.pin_message(chat, message, notify=True)
        """
        return await self._pin(entity, message, unpin=False, notify=notify, pm_oneside=pm_oneside)

    async def unpin_message(
            self: 'TelegramClient',
            entity: 'hints.EntityLike',
            message: 'typing.Optional[hints.MessageIDLike]' = None,
            *,
            notify: bool = False
    ):
        """
        Unpins a message in a chat.

        If no message ID is specified, all pinned messages will be unpinned.

        See also `Message.unpin() <telethon.tl.custom.message.Message.unpin>`.

        Arguments
            entity (`entity`):
                The chat where the message should be pinned.

            message (`int` | `Message <telethon.tl.custom.message.Message>`):
                The message or the message ID to unpin. If it's
                `None`, all messages will be unpinned instead.

        Example
            .. code-block:: python

                # Unpin all messages from a chat
                await client.unpin_message(chat)
        """
        return await self._pin(entity, message, unpin=True, notify=notify)

    async def _pin(self, entity, message, *, unpin, notify=False, pm_oneside=False):
        message = utils.get_message_id(message) or 0
        entity = await self.get_input_entity(entity)
        if message <= 0:  # old behaviour accepted negative IDs to unpin
            await self(functions.messages.UnpinAllMessagesRequest(entity))
            return

        request = functions.messages.UpdatePinnedMessageRequest(
            peer=entity,
            id=message,
            silent=not notify,
            unpin=unpin,
            pm_oneside=pm_oneside
        )
        result = await self(request)

        # Unpinning does not produce a service message.
        # Pinning a message that was already pinned also produces no service message.
        # Pinning a message in your own chat does not produce a service message,
        # but pinning on a private conversation with someone else does.
        if unpin or not result.updates:
            return

        # Pinning a message that doesn't exist would RPC-error earlier
        return self._get_response_message(request, result, entity)

    # endregion

    # endregion
