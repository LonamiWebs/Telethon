from .common import EventBuilder, EventCommon, name_inner_event
from .. import utils
from ..tl import types


@name_inner_event
class ChatAction(EventBuilder):
    """
    Occurs on certain chat actions:

    * Whenever a new chat is created.
    * Whenever a chat's title or photo is changed or removed.
    * Whenever a new message is pinned.
    * Whenever a user scores in a game.
    * Whenever a user joins or is added to the group.
    * Whenever a user is removed or leaves a group if it has
      less than 50 members or the removed user was a bot.

    Note that "chat" refers to "small group, megagroup and broadcast
    channel", whereas "group" refers to "small group and megagroup" only.

    Example
        .. code-block:: python

            from telethon import events

            @client.on(events.ChatAction)
            async def handler(event):
                # Welcome every new user
                if event.user_joined:
                    await event.reply('Welcome to the group!')
    """

    @classmethod
    def build(cls, update, others=None, self_id=None):
        # Rely on specific pin updates for unpins, but otherwise ignore them
        # for new pins (we'd rather handle the new service message with pin,
        # so that we can act on that message').
        if isinstance(update, types.UpdatePinnedChannelMessages) and not update.pinned:
            return cls.Event(types.PeerChannel(update.channel_id),
                             pin_ids=update.messages,
                             pin=update.pinned)

        elif isinstance(update, types.UpdatePinnedMessages) and not update.pinned:
            return cls.Event(update.peer,
                             pin_ids=update.messages,
                             pin=update.pinned)

        elif isinstance(update, types.UpdateChatParticipantAdd):
            return cls.Event(types.PeerChat(update.chat_id),
                             added_by=update.inviter_id or True,
                             users=update.user_id)

        elif isinstance(update, types.UpdateChatParticipantDelete):
            return cls.Event(types.PeerChat(update.chat_id),
                             kicked_by=True,
                             users=update.user_id)

        # UpdateChannel is sent if we leave a channel, and the update._entities
        # set by _process_update would let us make some guesses. However it's
        # better not to rely on this. Rely only in MessageActionChatDeleteUser.

        elif (isinstance(update, (
                types.UpdateNewMessage, types.UpdateNewChannelMessage))
              and isinstance(update.message, types.MessageService)):
            msg = update.message
            action = update.message.action
            if isinstance(action, types.MessageActionChatJoinedByLink):
                return cls.Event(msg,
                                 added_by=True,
                                 users=msg.from_id)
            elif isinstance(action, types.MessageActionChatAddUser):
                # If a user adds itself, it means they joined via the public chat username
                added_by = ([msg.sender_id] == action.users) or msg.from_id
                return cls.Event(msg,
                                 added_by=added_by,
                                 users=action.users)
            elif isinstance(action, types.MessageActionChatDeleteUser):
                return cls.Event(msg,
                                 kicked_by=utils.get_peer_id(msg.from_id) if msg.from_id else True,
                                 users=action.user_id)
            elif isinstance(action, types.MessageActionChatCreate):
                return cls.Event(msg,
                                 users=action.users,
                                 created=True,
                                 new_title=action.title)
            elif isinstance(action, types.MessageActionChannelCreate):
                return cls.Event(msg,
                                 created=True,
                                 users=msg.from_id,
                                 new_title=action.title)
            elif isinstance(action, types.MessageActionChatEditTitle):
                return cls.Event(msg,
                                 users=msg.from_id,
                                 new_title=action.title)
            elif isinstance(action, types.MessageActionChatEditPhoto):
                return cls.Event(msg,
                                 users=msg.from_id,
                                 new_photo=action.photo)
            elif isinstance(action, types.MessageActionChatDeletePhoto):
                return cls.Event(msg,
                                 users=msg.from_id,
                                 new_photo=True)
            elif isinstance(action, types.MessageActionPinMessage) and msg.reply_to:
                return cls.Event(msg,
                                 pin_ids=[msg.reply_to_msg_id])
            elif isinstance(action, types.MessageActionGameScore):
                return cls.Event(msg,
                                 new_score=action.score)

        elif isinstance(update, types.UpdateChannelParticipant) \
                and bool(update.new_participant) != bool(update.prev_participant):
            # If members are hidden, bots will receive this update instead,
            # as there won't be a service message. Promotions and demotions
            # seem to have both new and prev participant, which are ignored
            # by this event.
            return cls.Event(types.PeerChannel(update.channel_id),
                             users=update.user_id,
                             added_by=update.actor_id if update.new_participant else None,
                             kicked_by=update.actor_id if update.prev_participant else None)

    class Event(EventCommon):
        """
        Represents the event of a new chat action.

        Members:
            action_message  (`MessageAction <https://tl.telethon.dev/types/message_action.html>`_):
                The message invoked by this Chat Action.

            new_pin (`bool`):
                `True` if there is a new pin.

            new_photo (`bool`):
                `True` if there's a new chat photo (or it was removed).

            photo (:tl:`Photo`, optional):
                The new photo (or `None` if it was removed).

            user_added (`bool`):
                `True` if the user was added by some other.

            user_joined (`bool`):
                `True` if the user joined on their own.

            user_left (`bool`):
                `True` if the user left on their own.

            user_kicked (`bool`):
                `True` if the user was kicked by some other.

            created (`bool`, optional):
                `True` if this chat was just created.

            new_title (`str`, optional):
                The new title string for the chat, if applicable.

            new_score (`str`, optional):
                The new score string for the game, if applicable.

            unpin (`bool`):
                `True` if the existing pin gets unpinned.
        """

        def __init__(self, where, new_photo=None,
                     added_by=None, kicked_by=None, created=None,
                     users=None, new_title=None, pin_ids=None, pin=None, new_score=None):
            if isinstance(where, types.MessageService):
                self.action_message = where
                where = where.peer_id
            else:
                self.action_message = None

            # TODO needs some testing (can there be more than one id, and do they follow pin order?)
            #      same in get_pinned_message
            super().__init__(chat_peer=where, msg_id=pin_ids[0] if pin_ids else None)

            self.new_pin = pin_ids is not None
            self._pin_ids = pin_ids
            self._pinned_messages = None

            self.new_photo = new_photo is not None
            self.photo = \
                new_photo if isinstance(new_photo, types.Photo) else None

            self._added_by = None
            self._kicked_by = None
            self.user_added = self.user_joined = self.user_left = \
                self.user_kicked = self.unpin = False

            if added_by is True:
                self.user_joined = True
            elif added_by:
                self.user_added = True
                self._added_by = added_by

            # If `from_id` was not present (it's `True`) or the affected
            # user was "kicked by itself", then it left. Else it was kicked.
            if kicked_by is True or (users is not None and kicked_by == users):
                self.user_left = True
            elif kicked_by:
                self.user_kicked = True
                self._kicked_by = kicked_by

            self.created = bool(created)

            if isinstance(users, list):
                self._user_ids = [utils.get_peer_id(u) for u in users]
            elif users:
                self._user_ids = [utils.get_peer_id(users)]
            else:
                self._user_ids = []

            self._users = None
            self._input_users = None
            self.new_title = new_title
            self.new_score = new_score
            self.unpin = not pin

        def _set_client(self, client):
            super()._set_client(client)
            if self.action_message:
                self.action_message._finish_init(client, self._entities, None)

        async def respond(self, *args, **kwargs):
            """
            Responds to the chat action message (not as a reply). Shorthand for
            `telethon.client.messages.MessageMethods.send_message` with
            ``entity`` already set.
            """
            return await self._client.send_message(
                await self.get_input_chat(), *args, **kwargs)

        async def reply(self, *args, **kwargs):
            """
            Replies to the chat action message (as a reply). Shorthand for
            `telethon.client.messages.MessageMethods.send_message` with
            both ``entity`` and ``reply_to`` already set.

            Has the same effect as `respond` if there is no message.
            """
            if not self.action_message:
                return await self.respond(*args, **kwargs)

            kwargs['reply_to'] = self.action_message.id
            return await self._client.send_message(
                await self.get_input_chat(), *args, **kwargs)

        async def delete(self, *args, **kwargs):
            """
            Deletes the chat action message. You're responsible for checking
            whether you have the permission to do so, or to except the error
            otherwise. Shorthand for
            `telethon.client.messages.MessageMethods.delete_messages` with
            ``entity`` and ``message_ids`` already set.

            Does nothing if no message action triggered this event.
            """
            if not self.action_message:
                return

            return await self._client.delete_messages(
                await self.get_input_chat(), [self.action_message],
                *args, **kwargs
            )

        async def get_pinned_message(self):
            """
            If ``new_pin`` is `True`, this returns the `Message
            <telethon.tl.custom.message.Message>` object that was pinned.
            """
            if self._pinned_messages is None:
                await self.get_pinned_messages()

            if self._pinned_messages:
                return self._pinned_messages[0]

        async def get_pinned_messages(self):
            """
            If ``new_pin`` is `True`, this returns a `list` of `Message
            <telethon.tl.custom.message.Message>` objects that were pinned.
            """
            if not self._pin_ids:
                return self._pin_ids  # either None or empty list

            chat = await self.get_input_chat()
            if chat:
                self._pinned_messages = await self._client.get_messages(
                    self._input_chat, ids=self._pin_ids)

            return self._pinned_messages

        @property
        def added_by(self):
            """
            The user who added ``users``, if applicable (`None` otherwise).
            """
            if self._added_by and not isinstance(self._added_by, types.User):
                aby = self._entities.get(utils.get_peer_id(self._added_by))
                if aby:
                    self._added_by = aby

            return self._added_by

        async def get_added_by(self):
            """
            Returns `added_by` but will make an API call if necessary.
            """
            if not self.added_by and self._added_by:
                self._added_by = await self._client.get_entity(self._added_by)

            return self._added_by

        @property
        def kicked_by(self):
            """
            The user who kicked ``users``, if applicable (`None` otherwise).
            """
            if self._kicked_by and not isinstance(self._kicked_by, types.User):
                kby = self._entities.get(utils.get_peer_id(self._kicked_by))
                if kby:
                    self._kicked_by = kby

            return self._kicked_by

        async def get_kicked_by(self):
            """
            Returns `kicked_by` but will make an API call if necessary.
            """
            if not self.kicked_by and self._kicked_by:
                self._kicked_by = await self._client.get_entity(self._kicked_by)

            return self._kicked_by

        @property
        def user(self):
            """
            The first user that takes part in this action. For example, who joined.

            Might be `None` if the information can't be retrieved or
            there is no user taking part.
            """
            if self.users:
                return self._users[0]

        async def get_user(self):
            """
            Returns `user` but will make an API call if necessary.
            """
            if self.users or await self.get_users():
                return self._users[0]

        @property
        def input_user(self):
            """
            Input version of the ``self.user`` property.
            """
            if self.input_users:
                return self._input_users[0]

        async def get_input_user(self):
            """
            Returns `input_user` but will make an API call if necessary.
            """
            if self.input_users or await self.get_input_users():
                return self._input_users[0]

        @property
        def user_id(self):
            """
            Returns the marked signed ID of the first user, if any.
            """
            if self._user_ids:
                return self._user_ids[0]

        @property
        def users(self):
            """
            A list of users that take part in this action. For example, who joined.

            Might be empty if the information can't be retrieved or there
            are no users taking part.
            """
            if not self._user_ids:
                return []

            if self._users is None:
                self._users = [
                    self._entities[user_id]
                    for user_id in self._user_ids
                    if user_id in self._entities
                ]

            return self._users

        async def get_users(self):
            """
            Returns `users` but will make an API call if necessary.
            """
            if not self._user_ids:
                return []

            # Note: we access the property first so that it fills if needed
            if (self.users is None or len(self._users) != len(self._user_ids)) and self.action_message:
                await self.action_message._reload_message()
                self._users = [
                    u for u in self.action_message.action_entities
                    if isinstance(u, (types.User, types.UserEmpty))]

            return self._users

        @property
        def input_users(self):
            """
            Input version of the ``self.users`` property.
            """
            if self._input_users is None and self._user_ids:
                self._input_users = []
                for user_id in self._user_ids:
                    # First try to get it from our entities
                    try:
                        self._input_users.append(utils.get_input_peer(self._entities[user_id]))
                        continue
                    except (KeyError, TypeError):
                        pass

                    # If missing, try from the entity cache
                    try:
                        self._input_users.append(self._client._mb_entity_cache.get(
                            utils.resolve_id(user_id)[0])._as_input_peer())
                        continue
                    except AttributeError:
                        pass

            return self._input_users or []

        async def get_input_users(self):
            """
            Returns `input_users` but will make an API call if necessary.
            """
            if not self._user_ids:
                return []

            # Note: we access the property first so that it fills if needed
            if (self.input_users is None or len(self._input_users) != len(self._user_ids)) and self.action_message:
                self._input_users = [
                    utils.get_input_peer(u)
                    for u in self.action_message.action_entities
                    if isinstance(u, (types.User, types.UserEmpty))]

            return self._input_users or []

        @property
        def user_ids(self):
            """
            Returns the marked signed ID of the users, if any.
            """
            if self._user_ids:
                return self._user_ids[:]
