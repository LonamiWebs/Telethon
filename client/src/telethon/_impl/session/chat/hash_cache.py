from typing import Any, Optional, Sequence, Type, TypeAlias

from ...tl import abcs, types
from .peer_ref import ChannelRef, GroupRef, PeerRef, UserRef

PeerRefType: TypeAlias = Type[UserRef] | Type[ChannelRef] | Type[GroupRef]


class ChatHashCache:
    __slots__ = ("_hash_map", "_self_id", "_self_bot")

    def __init__(self, self_user: Optional[tuple[int, bool]]) -> None:
        self._hash_map: dict[int, tuple[PeerRefType, int]] = {}
        self._self_id = self_user[0] if self_user else None
        self._self_bot = self_user[1] if self_user else False

    @property
    def self_id(self) -> int:
        assert self._self_id is not None
        return self._self_id

    @property
    def is_self_bot(self) -> bool:
        return self._self_bot

    def set_self_user(self, identifier: int, bot: bool) -> None:
        self._self_id = identifier
        self._self_bot = bot

    def get(self, identifier: int) -> Optional[PeerRef]:
        if (entry := self._hash_map.get(identifier)) is not None:
            cls, authorization = entry
            return cls(identifier, authorization)
        else:
            return None

    def clear(self) -> None:
        self._hash_map.clear()
        self._self_id = None
        self._self_bot = False

    def _has(self, identifier: int) -> bool:
        return identifier in self._hash_map

    def _has_peer(self, peer: abcs.Peer) -> bool:
        if isinstance(peer, types.PeerUser):
            return self._has(peer.user_id)
        elif isinstance(peer, types.PeerChat):
            return True  # no hash needed, so we always have it
        elif isinstance(peer, types.PeerChannel):
            return self._has(peer.channel_id)
        else:
            raise RuntimeError("unexpected case")

    def _has_dialog_peer(self, peer: abcs.DialogPeer) -> bool:
        if isinstance(peer, types.DialogPeer):
            return self._has_peer(peer.peer)
        elif isinstance(peer, types.DialogPeerFolder):
            return True
        else:
            raise RuntimeError("unexpected case")

    def _has_notify_peer(self, peer: abcs.NotifyPeer) -> bool:
        if isinstance(peer, types.NotifyPeer):
            return self._has_peer(peer.peer)
        elif isinstance(peer, types.NotifyForumTopic):
            return self._has_peer(peer.peer)
        elif isinstance(
            peer, (types.NotifyUsers, types.NotifyChats, types.NotifyBroadcasts)
        ):
            return True
        else:
            raise RuntimeError("unexpected case")

    def _has_button(self, button: abcs.KeyboardButton) -> bool:
        if isinstance(button, types.InputKeyboardButtonUrlAuth):
            return self._has_user(button.bot)
        elif isinstance(button, types.InputKeyboardButtonUserProfile):
            return self._has_user(button.user_id)
        elif isinstance(button, types.KeyboardButtonUserProfile):
            return self._has(button.user_id)
        else:
            return True

    def _has_entity(self, entity: abcs.MessageEntity) -> bool:
        if isinstance(entity, types.MessageEntityMentionName):
            return self._has(entity.user_id)
        elif isinstance(entity, types.InputMessageEntityMentionName):
            return self._has_user(entity.user_id)
        else:
            return True

    def _has_user(self, peer: abcs.InputUser) -> bool:
        if isinstance(peer, (types.InputUserEmpty, types.InputUserSelf)):
            return True
        elif isinstance(peer, types.InputUser):
            return self._has(peer.user_id)
        elif isinstance(peer, types.InputUserFromMessage):
            return self._has(peer.user_id)
        else:
            raise RuntimeError("unexpected case")

    def _has_participant(self, participant: abcs.ChatParticipant) -> bool:
        if isinstance(participant, types.ChatParticipant):
            return self._has(participant.user_id) and self._has(participant.inviter_id)
        elif isinstance(participant, types.ChatParticipantCreator):
            return self._has(participant.user_id)
        elif isinstance(participant, types.ChatParticipantAdmin):
            return self._has(participant.user_id) and self._has(participant.inviter_id)
        else:
            raise RuntimeError("unexpected case")

    def _has_channel_participant(self, participant: abcs.ChannelParticipant) -> bool:
        if isinstance(participant, types.ChannelParticipant):
            return self._has(participant.user_id)
        elif isinstance(participant, types.ChannelParticipantSelf):
            return self._has(participant.user_id) and self._has(participant.inviter_id)
        elif isinstance(participant, types.ChannelParticipantCreator):
            return self._has(participant.user_id)
        elif isinstance(participant, types.ChannelParticipantAdmin):
            return (
                self._has(participant.user_id)
                and (
                    participant.inviter_id is None or self._has(participant.inviter_id)
                )
                and self._has(participant.promoted_by)
            )
        elif isinstance(participant, types.ChannelParticipantBanned):
            return self._has_peer(participant.peer) and self._has(participant.kicked_by)
        elif isinstance(participant, types.ChannelParticipantLeft):
            return self._has_peer(participant.peer)
        else:
            raise RuntimeError("unexpected case")

    def extend(self, users: Sequence[abcs.User], chats: Sequence[abcs.Chat]) -> bool:
        # See https://core.telegram.org/api/min for "issues" with "min constructors".
        success = True

        for user in users:
            if isinstance(user, types.UserEmpty):
                pass
            elif isinstance(user, types.User):
                if not user.min and user.access_hash is not None:
                    self._hash_map[user.id] = (UserRef, user.access_hash)
                else:
                    success &= user.id in self._hash_map
            else:
                raise RuntimeError("unexpected case")

        for chat in chats:
            if isinstance(chat, (types.ChatEmpty, types.Chat, types.ChatForbidden)):
                pass
            elif isinstance(chat, types.Channel):
                if not chat.min and chat.access_hash is not None:
                    self._hash_map[chat.id] = (ChannelRef, chat.access_hash)
                else:
                    success &= chat.id in self._hash_map
            elif isinstance(chat, types.ChannelForbidden):
                self._hash_map[chat.id] = (ChannelRef, chat.access_hash)
            else:
                raise RuntimeError("unexpected case")

        return success

    def extend_from_updates(self, updates: abcs.Updates) -> bool:
        if isinstance(updates, types.UpdatesTooLong):
            return True
        elif isinstance(updates, types.UpdateShortMessage):
            return self._has(updates.user_id)
        elif isinstance(updates, types.UpdateShortChatMessage):
            return self._has(updates.from_id)
        elif isinstance(updates, types.UpdateShort):
            success = True
            update = updates.update

            # In Python, we get to cheat rather than having hundreds of `if isinstance`
            for field in ("message",):
                message = getattr(update, field, None)
                if isinstance(message, abcs.Message):
                    success &= self.extend_from_message(message)

            for field in ("user_id", "inviter_id", "channel_id", "bot_id", "actor_id"):
                int_id = getattr(update, field, None)
                if isinstance(int_id, int):
                    success &= self._has(int_id)

            for field in ("from_id", "peer"):
                peer = getattr(update, field, None)
                if isinstance(peer, abcs.Peer):
                    success &= self._has_peer(peer)
                elif isinstance(peer, abcs.DialogPeer):
                    success &= self._has_dialog_peer(peer)
                elif isinstance(peer, abcs.NotifyPeer):
                    success &= self._has_notify_peer(peer)

            return success
        elif isinstance(updates, types.UpdatesCombined):
            return self.extend(updates.users, updates.chats)
        elif isinstance(updates, types.Updates):
            return self.extend(updates.users, updates.chats)
        elif isinstance(updates, types.UpdateShortSentMessage):
            return True
        else:
            raise RuntimeError("unexpected case")

    def extend_from_message(self, message: abcs.Message) -> bool:
        if isinstance(message, types.MessageEmpty):
            return message.peer_id is None or self._has_peer(message.peer_id)
        elif isinstance(message, types.Message):
            success = True

            if message.from_id is not None:
                success &= self._has_peer(message.from_id)

            success &= self._has_peer(message.peer_id)

            if isinstance(message.fwd_from, types.MessageFwdHeader):
                if message.fwd_from.from_id:
                    success &= self._has_peer(message.fwd_from.from_id)
                if message.fwd_from.saved_from_peer:
                    success &= self._has_peer(message.fwd_from.saved_from_peer)
            elif message.fwd_from is not None:
                raise RuntimeError("unexpected case")

            if isinstance(message.reply_to, types.MessageReplyHeader):
                if message.reply_to.reply_to_peer_id:
                    success &= self._has_peer(message.reply_to.reply_to_peer_id)
            elif message.reply_to is not None:
                raise RuntimeError("unexpected case")

            if message.reply_markup is not None:
                if isinstance(message.reply_markup, types.ReplyKeyboardMarkup):
                    for row in message.reply_markup.rows:
                        if isinstance(row, types.KeyboardButtonRow):
                            for button in row.buttons:
                                success &= self._has_button(button)
                elif isinstance(message.reply_markup, types.ReplyInlineMarkup):
                    for row in message.reply_markup.rows:
                        if isinstance(row, types.KeyboardButtonRow):
                            for button in row.buttons:
                                success &= self._has_button(button)

            if message.entities:
                for entity in message.entities:
                    success &= self._has_entity(entity)

            if isinstance(message.replies, types.MessageReplies):
                if message.replies.recent_repliers:
                    for p in message.replies.recent_repliers:
                        success &= self._has_peer(p)
            elif message.replies is not None:
                raise RuntimeError("unexpected case")

            if isinstance(message.reactions, types.MessageReactions):
                if message.reactions.recent_reactions:
                    for r in message.reactions.recent_reactions:
                        if isinstance(r, types.MessagePeerReaction):
                            success &= self._has_peer(r.peer_id)
                        else:
                            raise RuntimeError("unexpected case")
            elif message.reactions is not None:
                raise RuntimeError("unexpected case")

            return success
        elif isinstance(message, types.MessageService):
            success = True

            if message.from_id:
                success &= self._has_peer(message.from_id)

            if message.peer_id:
                success &= self._has_peer(message.peer_id)

            if isinstance(message.reply_to, types.MessageReplyHeader):
                if message.reply_to.reply_to_peer_id:
                    success &= self._has_peer(message.reply_to.reply_to_peer_id)
            elif message.reply_to is not None:
                raise RuntimeError("unexpected case")

            for field in ("user_id", "inviter_id", "channel_id"):
                int_id = getattr(message.action, field, None)
                if isinstance(int_id, int):
                    success &= self._has(int_id)

            for field in ("from_id", "to_id", "peer"):
                peer = getattr(message.action, field, None)
                if isinstance(peer, abcs.Peer):
                    success &= self._has_peer(peer)
                elif isinstance(peer, abcs.DialogPeer):
                    success &= self._has_dialog_peer(peer)
                elif isinstance(peer, abcs.NotifyPeer):
                    success &= self._has_notify_peer(peer)

            for field in ("users",):
                user: Any
                users = getattr(message.action, field, None)
                if isinstance(users, list):
                    for user in users:
                        if isinstance(user, int):
                            success &= self._has(user)

            return success
        else:
            raise RuntimeError("unexpected case")
