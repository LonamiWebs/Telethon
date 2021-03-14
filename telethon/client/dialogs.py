import asyncio
import inspect
import itertools
import typing

from .. import helpers, utils, hints, errors
from ..requestiter import RequestIter
from ..tl import types, functions, custom

_MAX_CHUNK_SIZE = 100

if typing.TYPE_CHECKING:
    from .telegramclient import TelegramClient


def _dialog_message_key(peer, message_id):
    """
    Get the key to get messages from a dialog.

    We cannot just use the message ID because channels share message IDs,
    and the peer ID is required to distinguish between them. But it is not
    necessary in small group chats and private chats.
    """
    return (peer.channel_id if isinstance(peer, types.PeerChannel) else None), message_id


class _DialogsIter(RequestIter):
    async def _init(
            self, offset_date, offset_id, offset_peer, ignore_pinned, ignore_migrated, folder
    ):
        self.request = functions.messages.GetDialogsRequest(
            offset_date=offset_date,
            offset_id=offset_id,
            offset_peer=offset_peer,
            limit=1,
            hash=0,
            exclude_pinned=ignore_pinned,
            folder_id=folder
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
                    for x in itertools.chain(r.users, r.chats)
                    if not isinstance(x, (types.UserEmpty, types.ChatEmpty))}

        messages = {}
        for m in r.messages:
            m._finish_init(self.client, entities, None)
            messages[_dialog_message_key(m.peer_id, m.id)] = m

        for d in r.dialogs:
            # We check the offset date here because Telegram may ignore it
            message = messages.get(_dialog_message_key(d.peer, d.top_message))
            if self.offset_date:
                date = getattr(message, 'date', None)
                if not date or date.timestamp() > self.offset_date.timestamp():
                    continue

            peer_id = utils.get_peer_id(d.peer)
            if peer_id not in self.seen:
                self.seen.add(peer_id)
                if peer_id not in entities:
                    # > In which case can a UserEmpty appear in the list of banned members?
                    # > In a very rare cases. This is possible but isn't an expected behavior.
                    # Real world example: https://t.me/TelethonChat/271471
                    continue

                cd = custom.Dialog(self.client, d, entities, message)
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

        # We can't use `messages[-1]` as the offset ID / date.
        # Why? Because pinned dialogs will mess with the order
        # in this list. Instead, we find the last dialog which
        # has a message, and use it as an offset.
        last_message = next(filter(None, (
            messages.get(_dialog_message_key(d.peer, d.top_message))
            for d in reversed(r.dialogs)
        )), None)

        self.request.exclude_pinned = True
        self.request.offset_id = last_message.id if last_message else 0
        self.request.offset_date = last_message.date if last_message else None
        self.request.offset_peer = self.buffer[-1].input_entity


class _DraftsIter(RequestIter):
    async def _init(self, entities, **kwargs):
        if not entities:
            r = await self.client(functions.messages.GetAllDraftsRequest())
            items = r.updates
        else:
            peers = []
            for entity in entities:
                peers.append(types.InputDialogPeer(
                    await self.client.get_input_entity(entity)))

            r = await self.client(functions.messages.GetPeerDialogsRequest(peers))
            items = r.dialogs

        # TODO Maybe there should be a helper method for this?
        entities = {utils.get_peer_id(x): x
                    for x in itertools.chain(r.users, r.chats)}

        self.buffer.extend(
            custom.Draft(self.client, entities[utils.get_peer_id(d.peer)], d.draft)
            for d in items
        )

    async def _load_next_chunk(self):
        return []


class DialogMethods:

    # region Public methods

    def iter_dialogs(
            self: 'TelegramClient',
            limit: float = None,
            *,
            offset_date: 'hints.DateLike' = None,
            offset_id: int = 0,
            offset_peer: 'hints.EntityLike' = types.InputPeerEmpty(),
            ignore_pinned: bool = False,
            ignore_migrated: bool = False,
            folder: int = None,
            archived: bool = None
    ) -> _DialogsIter:
        """
        Iterator over the dialogs (open conversations/subscribed channels).

        The order is the same as the one seen in official applications
        (first pinned, them from those with the most recent message to
        those with the oldest message).

        Arguments
            limit (`int` | `None`):
                How many dialogs to be retrieved as maximum. Can be set to
                `None` to retrieve all dialogs. Note that this may take
                whole minutes if you have hundreds of dialogs, as Telegram
                will tell the library to slow down through a
                ``FloodWaitError``.

            offset_date (`datetime`, optional):
                The offset date to be used.

            offset_id (`int`, optional):
                The message ID to be used as an offset.

            offset_peer (:tl:`InputPeer`, optional):
                The peer to be used as an offset.

            ignore_pinned (`bool`, optional):
                Whether pinned dialogs should be ignored or not.
                When set to `True`, these won't be yielded at all.

            ignore_migrated (`bool`, optional):
                Whether :tl:`Chat` that have ``migrated_to`` a :tl:`Channel`
                should be included or not. By default all the chats in your
                dialogs are returned, but setting this to `True` will ignore
                (i.e. skip) them in the same way official applications do.

            folder (`int`, optional):
                The folder from which the dialogs should be retrieved.

                If left unspecified, all dialogs (including those from
                folders) will be returned.

                If set to ``0``, all dialogs that don't belong to any
                folder will be returned.

                If set to a folder number like ``1``, only those from
                said folder will be returned.

                By default Telegram assigns the folder ID ``1`` to
                archived chats, so you should use that if you need
                to fetch the archived dialogs.

            archived (`bool`, optional):
                Alias for `folder`. If unspecified, all will be returned,
                `False` implies ``folder=0`` and `True` implies ``folder=1``.
        Yields
            Instances of `Dialog <telethon.tl.custom.dialog.Dialog>`.

        Example
            .. code-block:: python

                # Print all dialog IDs and the title, nicely formatted
                async for dialog in client.iter_dialogs():
                    print('{:>14}: {}'.format(dialog.id, dialog.title))
        """
        if archived is not None:
            folder = 1 if archived else 0

        return _DialogsIter(
            self,
            limit,
            offset_date=offset_date,
            offset_id=offset_id,
            offset_peer=offset_peer,
            ignore_pinned=ignore_pinned,
            ignore_migrated=ignore_migrated,
            folder=folder
        )

    async def get_dialogs(self: 'TelegramClient', *args, **kwargs) -> 'hints.TotalList':
        """
        Same as `iter_dialogs()`, but returns a
        `TotalList <telethon.helpers.TotalList>` instead.

        Example
            .. code-block:: python

                # Get all open conversation, print the title of the first
                dialogs = await client.get_dialogs()
                first = dialogs[0]
                print(first.title)

                # Use the dialog somewhere else
                await client.send_message(first, 'hi')

                # Getting only non-archived dialogs (both equivalent)
                non_archived = await client.get_dialogs(folder=0)
                non_archived = await client.get_dialogs(archived=False)

                # Getting only archived dialogs (both equivalent)
                archived = await client.get_dialogs(folder=1)
                archived = await client.get_dialogs(archived=True)
        """
        return await self.iter_dialogs(*args, **kwargs).collect()

    get_dialogs.__signature__ = inspect.signature(iter_dialogs)

    def iter_drafts(
            self: 'TelegramClient',
            entity: 'hints.EntitiesLike' = None
    ) -> _DraftsIter:
        """
        Iterator over draft messages.

        The order is unspecified.

        Arguments
            entity (`hints.EntitiesLike`, optional):
                The entity or entities for which to fetch the draft messages.
                If left unspecified, all draft messages will be returned.

        Yields
            Instances of `Draft <telethon.tl.custom.draft.Draft>`.

        Example
            .. code-block:: python

                # Clear all drafts
                async for draft in client.get_drafts():
                    await draft.delete()

                # Getting the drafts with 'bot1' and 'bot2'
                async for draft in client.iter_drafts(['bot1', 'bot2']):
                    print(draft.text)
        """
        if entity and not utils.is_list_like(entity):
            entity = (entity,)

        # TODO Passing a limit here makes no sense
        return _DraftsIter(self, None, entities=entity)

    async def get_drafts(
            self: 'TelegramClient',
            entity: 'hints.EntitiesLike' = None
    ) -> 'hints.TotalList':
        """
        Same as `iter_drafts()`, but returns a list instead.

        Example
            .. code-block:: python

                # Get drafts, print the text of the first
                drafts = await client.get_drafts()
                print(drafts[0].text)

                # Get the draft in your chat
                draft = await client.get_drafts('me')
                print(drafts.text)
        """
        items = await self.iter_drafts(entity).collect()
        if not entity or utils.is_list_like(entity):
            return items
        else:
            return items[0]

    async def edit_folder(
            self: 'TelegramClient',
            entity: 'hints.EntitiesLike' = None,
            folder: typing.Union[int, typing.Sequence[int]] = None,
            *,
            unpack=None
    ) -> types.Updates:
        """
        Edits the folder used by one or more dialogs to archive them.

        Arguments
            entity (entities):
                The entity or list of entities to move to the desired
                archive folder.

            folder (`int`):
                The folder to which the dialog should be archived to.

                If you want to "archive" a dialog, use ``folder=1``.

                If you want to "un-archive" it, use ``folder=0``.

                You may also pass a list with the same length as
                `entities` if you want to control where each entity
                will go.

            unpack (`int`, optional):
                If you want to unpack an archived folder, set this
                parameter to the folder number that you want to
                delete.

                When you unpack a folder, all the dialogs inside are
                moved to the folder number 0.

                You can only use this parameter if the other two
                are not set.

        Returns
            The :tl:`Updates` object that the request produces.

        Example
            .. code-block:: python

                # Archiving the first 5 dialogs
                dialogs = await client.get_dialogs(5)
                await client.edit_folder(dialogs, 1)

                # Un-archiving the third dialog (archiving to folder 0)
                await client.edit_folder(dialog[2], 0)

                # Moving the first dialog to folder 0 and the second to 1
                dialogs = await client.get_dialogs(2)
                await client.edit_folder(dialogs, [0, 1])

                # Un-archiving all dialogs
                await client.archive(unpack=1)
        """
        if (entity is None) == (unpack is None):
            raise ValueError('You can only set either entities or unpack, not both')

        if unpack is not None:
            return await self(functions.folders.DeleteFolderRequest(
                folder_id=unpack
            ))

        if not utils.is_list_like(entity):
            entities = [await self.get_input_entity(entity)]
        else:
            entities = await asyncio.gather(
                *(self.get_input_entity(x) for x in entity))

        if folder is None:
            raise ValueError('You must specify a folder')
        elif not utils.is_list_like(folder):
            folder = [folder] * len(entities)
        elif len(entities) != len(folder):
            raise ValueError('Number of folders does not match number of entities')

        return await self(functions.folders.EditPeerFoldersRequest([
            types.InputFolderPeer(x, folder_id=y)
            for x, y in zip(entities, folder)
        ]))

    async def delete_dialog(
            self: 'TelegramClient',
            entity: 'hints.EntityLike',
            *,
            revoke: bool = False
    ):
        """
        Deletes a dialog (leaves a chat or channel).

        This method can be used as a user and as a bot. However,
        bots will only be able to use it to leave groups and channels
        (trying to delete a private conversation will do nothing).

        See also `Dialog.delete() <telethon.tl.custom.dialog.Dialog.delete>`.

        Arguments
            entity (entities):
                The entity of the dialog to delete. If it's a chat or
                channel, you will leave it. Note that the chat itself
                is not deleted, only the dialog, because you left it.

            revoke (`bool`, optional):
                On private chats, you may revoke the messages from
                the other peer too. By default, it's `False`. Set
                it to `True` to delete the history for both.

                This makes no difference for bot accounts, who can
                only leave groups and channels.

        Returns
            The :tl:`Updates` object that the request produces,
            or nothing for private conversations.

        Example
            .. code-block:: python

                # Deleting the first dialog
                dialogs = await client.get_dialogs(5)
                await client.delete_dialog(dialogs[0])

                # Leaving a channel by username
                await client.delete_dialog('username')
        """
        # If we have enough information (`Dialog.delete` gives it to us),
        # then we know we don't have to kick ourselves in deactivated chats.
        if isinstance(entity, types.Chat):
            deactivated = entity.deactivated
        else:
            deactivated = False

        entity = await self.get_input_entity(entity)
        ty = helpers._entity_type(entity)
        if ty == helpers._EntityType.CHANNEL:
            return await self(functions.channels.LeaveChannelRequest(entity))

        if ty == helpers._EntityType.CHAT and not deactivated:
            try:
                result = await self(functions.messages.DeleteChatUserRequest(
                    entity.chat_id, types.InputUserSelf(), revoke_history=revoke
                ))
            except errors.PeerIdInvalidError:
                # Happens if we didn't have the deactivated information
                result = None
        else:
            result = None

        if not await self.is_bot():
            await self(functions.messages.DeleteHistoryRequest(entity, 0, revoke=revoke))

        return result

    def conversation(
            self: 'TelegramClient',
            entity: 'hints.EntityLike',
            *,
            timeout: float = 60,
            total_timeout: float = None,
            max_messages: int = 100,
            exclusive: bool = True,
            replies_are_responses: bool = True) -> custom.Conversation:
        """
        Creates a `Conversation <telethon.tl.custom.conversation.Conversation>`
        with the given entity.

        This is not the same as just sending a message to create a "dialog"
        with them, but rather a way to easily send messages and await for
        responses or other reactions. Refer to its documentation for more.

        Arguments
            entity (`entity`):
                The entity with which a new conversation should be opened.

            timeout (`int` | `float`, optional):
                The default timeout (in seconds) *per action* to be used. You
                may also override this timeout on a per-method basis. By
                default each action can take up to 60 seconds (the value of
                this timeout).

            total_timeout (`int` | `float`, optional):
                The total timeout (in seconds) to use for the whole
                conversation. This takes priority over per-action
                timeouts. After these many seconds pass, subsequent
                actions will result in ``asyncio.TimeoutError``.

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

        Returns
            A `Conversation <telethon.tl.custom.conversation.Conversation>`.

        Example
            .. code-block:: python

                # <you> denotes outgoing messages you sent
                # <usr> denotes incoming response messages
                with bot.conversation(chat) as conv:
                    # <you> Hi!
                    conv.send_message('Hi!')

                    # <usr> Hello!
                    hello = conv.get_response()

                    # <you> Please tell me your name
                    conv.send_message('Please tell me your name')

                    # <usr> ?
                    name = conv.get_response().raw_text

                    while not any(x.isalpha() for x in name):
                        # <you> Your name didn't have any letters! Try again
                        conv.send_message("Your name didn't have any letters! Try again")

                        # <usr> Human
                        name = conv.get_response().raw_text

                    # <you> Thanks Human!
                    conv.send_message('Thanks {}!'.format(name))
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
