import itertools

from .users import UserMethods
from .. import utils
from ..requestiter import RequestIter
from ..tl import types, functions, custom

_MAX_CHUNK_SIZE = 100


class _DialogsIter(RequestIter):
    async def _init(
            self, offset_date, offset_id, offset_peer, ignore_migrated
    ):
        self.request = functions.messages.GetDialogsRequest(
            offset_date=offset_date,
            offset_id=offset_id,
            offset_peer=offset_peer,
            limit=1,
            hash=0
        )

        if self.limit <= 0:
            # Special case, get a single dialog and determine count
            dialogs = await self.client(self.request)
            self.total = getattr(dialogs, 'count', len(dialogs.dialogs))
            raise StopAsyncIteration

        self.seen = set()
        self.offset_date = offset_date
        self.ignore_migrated = ignore_migrated

    async def _load_next_chunk(self):
        self.request.limit = min(self.left, _MAX_CHUNK_SIZE)
        r = await self.client(self.request)

        self.total = getattr(r, 'count', len(r.dialogs))

        entities = {utils.get_peer_id(x): x
                    for x in itertools.chain(r.users, r.chats)}

        messages = {}
        for m in r.messages:
            m._finish_init(self, entities, None)
            messages[m.id] = m

        for d in r.dialogs:
            # We check the offset date here because Telegram may ignore it
            if self.offset_date:
                date = getattr(messages.get(
                    d.top_message, None), 'date', None)

                if not date or date.timestamp() > self.offset_date.timestamp():
                    continue

            peer_id = utils.get_peer_id(d.peer)
            if peer_id not in self.seen:
                self.seen.add(peer_id)
                cd = custom.Dialog(self, d, entities, messages)
                if cd.dialog.pts:
                    self.client._channel_pts[cd.id] = cd.dialog.pts

                if not self.ignore_migrated or getattr(
                        cd.entity, 'migrated_to', None) is None:
                    self.buffer.append(cd)

        if len(r.dialogs) < self.request.limit\
                or not isinstance(r, types.messages.DialogsSlice):
            # Less than we requested means we reached the end, or
            # we didn't get a DialogsSlice which means we got all.
            return True

        if self.request.offset_id == r.messages[-1].id:
            # In some very rare cases this will get stuck in an infinite
            # loop, where the offsets will get reused over and over. If
            # the new offset is the same as the one before, break already.
            return True

        self.request.offset_id = r.messages[-1].id
        self.request.exclude_pinned = True
        self.request.offset_date = r.messages[-1].date
        self.request.offset_peer =\
            entities[utils.get_peer_id(r.dialogs[-1].peer)]


class _DraftsIter(RequestIter):
    async def _init(self, **kwargs):
        r = await self.client(functions.messages.GetAllDraftsRequest())
        self.buffer.extend(custom.Draft._from_update(self.client, u)
                           for u in r.updates)

    async def _load_next_chunk(self):
        return []


class DialogMethods(UserMethods):

    # region Public methods

    def iter_dialogs(
            self, limit=None, *, offset_date=None, offset_id=0,
            offset_peer=types.InputPeerEmpty(), ignore_migrated=False
    ):
        """
        Returns an iterator over the dialogs, yielding 'limit' at most.
        Dialogs are the open "chats" or conversations with other people,
        groups you have joined, or channels you are subscribed to.

        Args:
            limit (`int` | `None`):
                How many dialogs to be retrieved as maximum. Can be set to
                ``None`` to retrieve all dialogs. Note that this may take
                whole minutes if you have hundreds of dialogs, as Telegram
                will tell the library to slow down through a
                ``FloodWaitError``.

            offset_date (`datetime`, optional):
                The offset date to be used.

            offset_id (`int`, optional):
                The message ID to be used as an offset.

            offset_peer (:tl:`InputPeer`, optional):
                The peer to be used as an offset.

            ignore_migrated (`bool`, optional):
                Whether :tl:`Chat` that have ``migrated_to`` a :tl:`Channel`
                should be included or not. By default all the chats in your
                dialogs are returned, but setting this to ``True`` will hide
                them in the same way official applications do.

        Yields:
            Instances of `telethon.tl.custom.dialog.Dialog`.
        """
        return _DialogsIter(
            self,
            limit,
            offset_date=offset_date,
            offset_id=offset_id,
            offset_peer=offset_peer,
            ignore_migrated=ignore_migrated
        )

    async def get_dialogs(self, *args, **kwargs):
        """
        Same as `iter_dialogs`, but returns a
        `TotalList <telethon.helpers.TotalList>` instead.
        """
        return await self.iter_dialogs(*args, **kwargs).collect()

    def iter_drafts(self):
        """
        Iterator over all open draft messages.

        Instances of `telethon.tl.custom.draft.Draft` are yielded.
        You can call `telethon.tl.custom.draft.Draft.set_message`
        to change the message or `telethon.tl.custom.draft.Draft.delete`
        among other things.
        """
        # TODO Passing a limit here makes no sense
        return _DraftsIter(self, None)

    async def get_drafts(self):
        """
        Same as :meth:`iter_drafts`, but returns a list instead.
        """
        return await self.iter_drafts().collect()

    def conversation(
            self, entity,
            *, timeout=60, total_timeout=None, max_messages=100,
            exclusive=True, replies_are_responses=True):
        """
        Creates a `Conversation <telethon.tl.custom.conversation.Conversation>`
        with the given entity so you can easily send messages and await for
        responses or other reactions. Refer to its documentation for more.

        Args:
            entity (`entity`):
                The entity with which a new conversation should be opened.

            timeout (`int` | `float`, optional):
                The default timeout *per action* to be used. You may also
                override this timeout on a per-method basis. By default each
                action can take up to 60 seconds (the value of this timeout).

            total_timeout (`int` | `float`, optional):
                The total timeout to use for the whole conversation. This
                takes priority over per-action timeouts. After these many
                seconds pass, subsequent actions will result in
                ``asyncio.TimeoutError``.

            max_messages (`int`, optional):
                The maximum amount of messages this conversation will
                remember. After these many messages arrive in the
                specified chat, subsequent actions will result in
                ``ValueError``.

            exclusive (`bool`, optional):
                By default, conversations are exclusive within a single
                chat. That means that while a conversation is open in a
                chat, you can't open another one in the same chat, unless
                you disable this flag.

                If you try opening an exclusive conversation for
                a chat where it's already open, it will raise
                ``AlreadyInConversationError``.

            replies_are_responses (`bool`, optional):
                Whether replies should be treated as responses or not.

                If the setting is enabled, calls to `conv.get_response
                <telethon.tl.custom.conversation.Conversation.get_response>`
                and a subsequent call to `conv.get_reply
                <telethon.tl.custom.conversation.Conversation.get_reply>`
                will return different messages, otherwise they may return
                the same message.

                Consider the following scenario with one outgoing message,
                1, and two incoming messages, the second one replying::

                                        Hello! <1
                    2> (reply to 1) Hi!
                    3> (reply to 1) How are you?

                And the following code:

                .. code-block:: python

                    async with client.conversation(chat) as conv:
                        msg1 = await conv.send_message('Hello!')
                        msg2 = await conv.get_response()
                        msg3 = await conv.get_reply()

                With the setting enabled, ``msg2`` will be ``'Hi!'`` and
                ``msg3`` be ``'How are you?'`` since replies are also
                responses, and a response was already returned.

                With the setting disabled, both ``msg2`` and ``msg3`` will
                be ``'Hi!'`` since one is a response and also a reply.

        Returns:
            A `Conversation <telethon.tl.custom.conversation.Conversation>`.
        """
        return custom.Conversation(
            self,
            entity,
            timeout=timeout,
            total_timeout=total_timeout,
            max_messages=max_messages,
            exclusive=exclusive,
            replies_are_responses=replies_are_responses

        )

    # endregion
