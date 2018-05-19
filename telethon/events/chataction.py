from .common import EventBuilder, EventCommon, name_inner_event
from .. import utils
from ..tl import types, functions


@name_inner_event
class ChatAction(EventBuilder):
    """
    Represents an action in a chat (such as user joined, left, or new pin).
    """
    def build(self, update):
        if isinstance(update, types.UpdateChannelPinnedMessage) and update.id == 0:
            # Telegram does not always send
            # UpdateChannelPinnedMessage for new pins
            # but always for unpin, with update.id = 0
            event = ChatAction.Event(types.PeerChannel(update.channel_id),
                                     unpin=True)

        elif isinstance(update, types.UpdateChatParticipantAdd):
            event = ChatAction.Event(types.PeerChat(update.chat_id),
                                     added_by=update.inviter_id or True,
                                     users=update.user_id)

        elif isinstance(update, types.UpdateChatParticipantDelete):
            event = ChatAction.Event(types.PeerChat(update.chat_id),
                                     kicked_by=True,
                                     users=update.user_id)

        elif (isinstance(update, (
                types.UpdateNewMessage, types.UpdateNewChannelMessage))
              and isinstance(update.message, types.MessageService)):
            msg = update.message
            action = update.message.action
            if isinstance(action, types.MessageActionChatJoinedByLink):
                event = ChatAction.Event(msg,
                                         added_by=True,
                                         users=msg.from_id)
            elif isinstance(action, types.MessageActionChatAddUser):
                event = ChatAction.Event(msg,
                                         added_by=msg.from_id or True,
                                         users=action.users)
            elif isinstance(action, types.MessageActionChatDeleteUser):
                event = ChatAction.Event(msg,
                                         kicked_by=msg.from_id or True,
                                         users=action.user_id)
            elif isinstance(action, types.MessageActionChatCreate):
                event = ChatAction.Event(msg,
                                         users=action.users,
                                         created=True,
                                         new_title=action.title)
            elif isinstance(action, types.MessageActionChannelCreate):
                event = ChatAction.Event(msg,
                                         created=True,
                                         users=msg.from_id,
                                         new_title=action.title)
            elif isinstance(action, types.MessageActionChatEditTitle):
                event = ChatAction.Event(msg,
                                         users=msg.from_id,
                                         new_title=action.title)
            elif isinstance(action, types.MessageActionChatEditPhoto):
                event = ChatAction.Event(msg,
                                         users=msg.from_id,
                                         new_photo=action.photo)
            elif isinstance(action, types.MessageActionChatDeletePhoto):
                event = ChatAction.Event(msg,
                                         users=msg.from_id,
                                         new_photo=True)
            elif isinstance(action, types.MessageActionPinMessage):
                # Telegram always sends this service message for new pins
                event = ChatAction.Event(msg,
                                         users=msg.from_id,
                                         new_pin=msg.reply_to_msg_id)
            else:
                return
        else:
            return

        event._entities = update._entities
        return self._filter_event(event)

    class Event(EventCommon):
        """
        Represents the event of a new chat action.

        Members:
            action_message  (`MessageAction <https://lonamiwebs.github.io/Telethon/types/message_action.html>`_):
                The message invoked by this Chat Action.

            new_pin (`bool`):
                ``True`` if there is a new pin.

            new_photo (`bool`):
                ``True`` if there's a new chat photo (or it was removed).

            photo (:tl:`Photo`, optional):
                The new photo (or ``None`` if it was removed).

            user_added (`bool`):
                ``True`` if the user was added by some other.

            user_joined (`bool`):
                ``True`` if the user joined on their own.

            user_left (`bool`):
                ``True`` if the user left on their own.

            user_kicked (`bool`):
                ``True`` if the user was kicked by some other.

            created (`bool`, optional):
                ``True`` if this chat was just created.

            new_title (`str`, optional):
                The new title string for the chat, if applicable.

            unpin (`bool`):
                ``True`` if the existing pin gets unpinned.
        """
        def __init__(self, where, new_pin=None, new_photo=None,
                     added_by=None, kicked_by=None, created=None,
                     users=None, new_title=None, unpin=None):
            if isinstance(where, types.MessageService):
                self.action_message = where
                where = where.to_id
            else:
                self.action_message = None

            super().__init__(chat_peer=where, msg_id=new_pin)

            self.new_pin = isinstance(new_pin, int)
            self._pinned_message = new_pin

            self.new_photo = new_photo is not None
            self.photo = \
                new_photo if isinstance(new_photo, types.Photo) else None

            self._added_by = None
            self._kicked_by = None
            self.user_added, self.user_joined, self.user_left,\
                self.user_kicked, self.unpin = (False, False, False, False, False)

            if added_by is True:
                self.user_joined = True
            elif added_by:
                self.user_added = True
                self._added_by = added_by

            if kicked_by is True:
                self.user_left = True
            elif kicked_by:
                self.user_kicked = True
                self._kicked_by = kicked_by

            self.created = bool(created)
            self._user_peers = users if isinstance(users, list) else [users]
            self._users = None
            self._input_users = None
            self.new_title = new_title
            self.unpin = unpin

        async def respond(self, *args, **kwargs):
            """
            Responds to the chat action message (not as a reply). Shorthand for
            `telethon.telegram_client.TelegramClient.send_message` with
            ``entity`` already set.
            """
            return await self._client.send_message(await self.input_chat, *args, **kwargs)

        async def reply(self, *args, **kwargs):
            """
            Replies to the chat action message (as a reply). Shorthand for
            `telethon.telegram_client.TelegramClient.send_message` with
            both ``entity`` and ``reply_to`` already set.

            Has the same effect as `respond` if there is no message.
            """
            if not self.action_message:
                return self.respond(*args, **kwargs)

            kwargs['reply_to'] = self.action_message.id
            return await self._client.send_message(await self.input_chat, *args, **kwargs)

        async def delete(self, *args, **kwargs):
            """
            Deletes the chat action message. You're responsible for checking
            whether you have the permission to do so, or to except the error
            otherwise. Shorthand for
            `telethon.telegram_client.TelegramClient.delete_messages` with
            ``entity`` and ``message_ids`` already set.

            Does nothing if no message action triggered this event.
            """
            if self.action_message:
                return await self._client.delete_messages(await self.input_chat,
                                                          [self.action_message],
                                                          *args, **kwargs)

        @property
        async def pinned_message(self):
            """
            If ``new_pin`` is ``True``, this returns the (:tl:`Message`)
            object that was pinned.
            """
            if self._pinned_message == 0:
                return None

            if isinstance(self._pinned_message, int) and await self.input_chat:
                r = await self._client(functions.channels.GetMessagesRequest(
                    self._input_chat, [self._pinned_message]
                ))
                try:
                    self._pinned_message = next(
                        x for x in r.messages
                        if isinstance(x, types.Message)
                        and x.id == self._pinned_message
                    )
                except StopIteration:
                    pass

            if isinstance(self._pinned_message, types.Message):
                return self._pinned_message

        @property
        async def added_by(self):
            """
            The user who added ``users``, if applicable (``None`` otherwise).
            """
            if self._added_by and not isinstance(self._added_by, types.User):
                self._added_by =\
                    self._entities.get(utils.get_peer_id(self._added_by))

                if not self._added_by:
                    self._added_by = await self._client.get_entity(self._added_by)

            return self._added_by

        @property
        async def kicked_by(self):
            """
            The user who kicked ``users``, if applicable (``None`` otherwise).
            """
            if self._kicked_by and not isinstance(self._kicked_by, types.User):
                self._kicked_by =\
                    self._entities.get(utils.get_peer_id(self._kicked_by))

                if not self._kicked_by:
                    self._kicked_by = await self._client.get_entity(self._kicked_by)

            return self._kicked_by

        @property
        async def user(self):
            """
            The first user that takes part in this action (e.g. joined).

            Might be ``None`` if the information can't be retrieved or
            there is no user taking part.
            """
            if await self.users:
                return self._users[0]

        @property
        async def input_user(self):
            """
            Input version of the ``self.user`` property.
            """
            if await self.input_users:
                return self._input_users[0]

        @property
        def user_id(self):
            """
            Returns the marked signed ID of the first user, if any.
            """
            if self._user_peers:
                return utils.get_peer_id(self._user_peers[0])

        @property
        async def users(self):
            """
            A list of users that take part in this action (e.g. joined).

            Might be empty if the information can't be retrieved or there
            are no users taking part.
            """
            if not self._user_peers:
                return []

            if self._users is None:
                have, missing = [], []
                for peer in self._user_peers:
                    user = self._entities.get(utils.get_peer_id(peer))
                    if user:
                        have.append(user)
                    else:
                        missing.append(peer)

                try:
                    missing = await self._client.get_entity(missing)
                except (TypeError, ValueError):
                    missing = []

                self._users = have + missing

            return self._users

        @property
        async def input_users(self):
            """
            Input version of the ``self.users`` property.
            """
            if self._input_users is None and self._user_peers:
                self._input_users = []
                for peer in self._user_peers:
                    try:
                        self._input_users.append(await self._client.get_input_entity(
                            peer
                        ))
                    except (TypeError, ValueError):
                        pass
            return self._input_users

        @property
        def user_ids(self):
            """
            Returns the marked signed ID of the users, if any.
            """
            if self._user_peers:
                return [utils.get_peer_id(u) for u in self._user_peers]
