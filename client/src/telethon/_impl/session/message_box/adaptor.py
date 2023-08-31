from typing import Optional

from ...tl import abcs, types
from ..chat.hash_cache import ChatHashCache
from .defs import ENTRY_ACCOUNT, ENTRY_SECRET, NO_SEQ, Gap, PtsInfo


def updates_(updates: types.Updates) -> types.UpdatesCombined:
    return types.UpdatesCombined(
        updates=updates.updates,
        users=updates.users,
        chats=updates.chats,
        date=updates.date,
        seq_start=updates.seq,
        seq=updates.seq,
    )


def update_short(short: types.UpdateShort) -> types.UpdatesCombined:
    return types.UpdatesCombined(
        updates=[short.update],
        users=[],
        chats=[],
        date=short.date,
        seq_start=NO_SEQ,
        seq=NO_SEQ,
    )


def update_short_message(
    short: types.UpdateShortMessage, self_id: int
) -> types.UpdatesCombined:
    return update_short(
        types.UpdateShort(
            update=types.UpdateNewMessage(
                message=types.Message(
                    out=short.out,
                    mentioned=short.mentioned,
                    media_unread=short.media_unread,
                    silent=short.silent,
                    post=False,
                    from_scheduled=False,
                    legacy=False,
                    edit_hide=False,
                    pinned=False,
                    noforwards=False,
                    reactions=None,
                    id=short.id,
                    from_id=types.PeerUser(
                        user_id=self_id if short.out else short.user_id
                    ),
                    peer_id=types.PeerChat(
                        chat_id=short.user_id,
                    ),
                    fwd_from=short.fwd_from,
                    via_bot_id=short.via_bot_id,
                    reply_to=short.reply_to,
                    date=short.date,
                    message=short.message,
                    media=None,
                    reply_markup=None,
                    entities=short.entities,
                    views=None,
                    forwards=None,
                    replies=None,
                    edit_date=None,
                    post_author=None,
                    grouped_id=None,
                    restriction_reason=None,
                    ttl_period=short.ttl_period,
                ),
                pts=short.pts,
                pts_count=short.pts_count,
            ),
            date=short.date,
        )
    )


def update_short_chat_message(
    short: types.UpdateShortChatMessage,
) -> types.UpdatesCombined:
    return update_short(
        types.UpdateShort(
            update=types.UpdateNewMessage(
                message=types.Message(
                    out=short.out,
                    mentioned=short.mentioned,
                    media_unread=short.media_unread,
                    silent=short.silent,
                    post=False,
                    from_scheduled=False,
                    legacy=False,
                    edit_hide=False,
                    pinned=False,
                    noforwards=False,
                    reactions=None,
                    id=short.id,
                    from_id=types.PeerUser(
                        user_id=short.from_id,
                    ),
                    peer_id=types.PeerChat(
                        chat_id=short.chat_id,
                    ),
                    fwd_from=short.fwd_from,
                    via_bot_id=short.via_bot_id,
                    reply_to=short.reply_to,
                    date=short.date,
                    message=short.message,
                    media=None,
                    reply_markup=None,
                    entities=short.entities,
                    views=None,
                    forwards=None,
                    replies=None,
                    edit_date=None,
                    post_author=None,
                    grouped_id=None,
                    restriction_reason=None,
                    ttl_period=short.ttl_period,
                ),
                pts=short.pts,
                pts_count=short.pts_count,
            ),
            date=short.date,
        )
    )


def update_short_sent_message(
    short: types.UpdateShortSentMessage,
) -> types.UpdatesCombined:
    return update_short(
        types.UpdateShort(
            update=types.UpdateNewMessage(
                message=types.MessageEmpty(
                    id=short.id,
                    peer_id=None,
                ),
                pts=short.pts,
                pts_count=short.pts_count,
            ),
            date=short.date,
        )
    )


def adapt(updates: abcs.Updates, chat_hashes: ChatHashCache) -> types.UpdatesCombined:
    if isinstance(updates, types.UpdatesTooLong):
        raise Gap
    elif isinstance(updates, types.UpdateShortMessage):
        return update_short_message(updates, chat_hashes.self_id)
    elif isinstance(updates, types.UpdateShortChatMessage):
        return update_short_chat_message(updates)
    elif isinstance(updates, types.UpdateShort):
        return update_short(updates)
    elif isinstance(updates, types.UpdatesCombined):
        return updates
    elif isinstance(updates, types.Updates):
        return updates_(updates)
    elif isinstance(updates, types.UpdateShortSentMessage):
        return update_short_sent_message(updates)
    else:
        raise RuntimeError("unexpected case")


def message_peer(message: abcs.Message) -> Optional[abcs.Peer]:
    if isinstance(message, types.MessageEmpty):
        return None
    elif isinstance(message, types.Message):
        return message.peer_id
    elif isinstance(message, types.MessageService):
        return message.peer_id
    else:
        raise RuntimeError("unexpected case")


def message_channel_id(message: abcs.Message) -> Optional[int]:
    peer = message_peer(message)
    return peer.channel_id if isinstance(peer, types.PeerChannel) else None


def pts_info_from_update(update: abcs.Update) -> Optional[PtsInfo]:
    if isinstance(update, types.UpdateNewMessage):
        assert not isinstance(message_peer(update.message), types.PeerChannel)
        return PtsInfo(ENTRY_ACCOUNT, update.pts, update.pts_count)
    elif isinstance(update, types.UpdateDeleteMessages):
        return PtsInfo(ENTRY_ACCOUNT, update.pts, update.pts_count)
    elif isinstance(update, types.UpdateNewEncryptedMessage):
        return PtsInfo(ENTRY_SECRET, update.qts, 1)
    elif isinstance(update, types.UpdateReadHistoryInbox):
        assert not isinstance(update.peer, types.PeerChannel)
        return PtsInfo(ENTRY_ACCOUNT, update.pts, update.pts_count)
    elif isinstance(update, types.UpdateReadHistoryOutbox):
        assert not isinstance(update.peer, types.PeerChannel)
        return PtsInfo(ENTRY_ACCOUNT, update.pts, update.pts_count)
    elif isinstance(update, types.UpdateWebPage):
        return PtsInfo(ENTRY_ACCOUNT, update.pts, update.pts_count)
    elif isinstance(update, types.UpdateReadMessagesContents):
        return PtsInfo(ENTRY_ACCOUNT, update.pts, update.pts_count)
    elif isinstance(update, types.UpdateChannelTooLong):
        if update.pts is not None:
            return PtsInfo(update.channel_id, update.pts, 0)
        else:
            return None
    elif isinstance(update, types.UpdateNewChannelMessage):
        channel_id = message_channel_id(update.message)
        if channel_id is not None:
            return PtsInfo(channel_id, update.pts, update.pts_count)
        else:
            return None
    elif isinstance(update, types.UpdateReadChannelInbox):
        return PtsInfo(update.channel_id, update.pts, 0)
    elif isinstance(update, types.UpdateDeleteChannelMessages):
        return PtsInfo(update.channel_id, update.pts, update.pts_count)
    elif isinstance(update, types.UpdateEditChannelMessage):
        channel_id = message_channel_id(update.message)
        if channel_id is not None:
            return PtsInfo(channel_id, update.pts, update.pts_count)
        else:
            return None
    elif isinstance(update, types.UpdateEditMessage):
        assert not isinstance(message_peer(update.message), types.PeerChannel)
        return PtsInfo(ENTRY_ACCOUNT, update.pts, update.pts_count)
    elif isinstance(update, types.UpdateChannelWebPage):
        return PtsInfo(update.channel_id, update.pts, update.pts_count)
    elif isinstance(update, types.UpdateFolderPeers):
        return PtsInfo(ENTRY_ACCOUNT, update.pts, update.pts_count)
    elif isinstance(update, types.UpdatePinnedMessages):
        assert not isinstance(update.peer, types.PeerChannel)
        return PtsInfo(ENTRY_ACCOUNT, update.pts, update.pts_count)
    elif isinstance(update, types.UpdatePinnedChannelMessages):
        return PtsInfo(update.channel_id, update.pts, update.pts_count)
    elif isinstance(update, types.UpdateChatParticipant):
        return PtsInfo(ENTRY_SECRET, update.qts, 0)
    elif isinstance(update, types.UpdateChannelParticipant):
        return PtsInfo(ENTRY_SECRET, update.qts, 0)
    elif isinstance(update, types.UpdateBotStopped):
        return PtsInfo(ENTRY_SECRET, update.qts, 0)
    elif isinstance(update, types.UpdateBotChatInviteRequester):
        return PtsInfo(ENTRY_SECRET, update.qts, 0)
    else:
        return None
