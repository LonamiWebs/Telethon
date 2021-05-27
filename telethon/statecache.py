import inspect

from .tl import types

# Which updates have the following fields?
_has_channel_id = []


# TODO EntityCache does the same. Reuse?
def _fill():
    for name in dir(types):
        update = getattr(types, name)
        if getattr(update, 'SUBCLASS_OF_ID', None) == 0x9f89304e:
            cid = update.CONSTRUCTOR_ID
            sig = inspect.signature(update.__init__)
            for param in sig.parameters.values():
                if param.name == 'channel_id' and param.annotation == int:
                    _has_channel_id.append(cid)

    if not _has_channel_id:
        raise RuntimeError('FIXME: Did the init signature or updates change?')


# We use a function to avoid cluttering the globals (with name/update/cid/doc)
_fill()


has_pts = frozenset(x.CONSTRUCTOR_ID for x in (
    types.UpdateNewMessage,
    types.UpdateDeleteMessages,
    types.UpdateReadHistoryInbox,
    types.UpdateReadHistoryOutbox,
    types.UpdateWebPage,
    types.UpdateReadMessagesContents,
    types.UpdateEditMessage,
    types.updates.State,
    types.updates.DifferenceTooLong,
    types.UpdateShortMessage,
    types.UpdateShortChatMessage,
    types.UpdateShortSentMessage
))
has_qts = frozenset(x.CONSTRUCTOR_ID for x in (
    types.UpdateBotStopped,
    types.UpdateNewEncryptedMessage,
    types.updates.State
))
has_date = frozenset(x.CONSTRUCTOR_ID for x in (
    types.UpdateUserPhoto,
    types.UpdateEncryption,
    types.UpdateEncryptedMessagesRead,
    types.UpdateChatParticipantAdd,
    types.updates.DifferenceEmpty,
    types.UpdateShortMessage,
    types.UpdateShortChatMessage,
    types.UpdateShort,
    types.UpdatesCombined,
    types.Updates,
    types.UpdateShortSentMessage,
))
has_channel_pts = frozenset(x.CONSTRUCTOR_ID for x in (
    types.UpdateChannelTooLong,
    types.UpdateNewChannelMessage,
    types.UpdateDeleteChannelMessages,
    types.UpdateEditChannelMessage,
    types.UpdateChannelWebPage,
    types.updates.ChannelDifferenceEmpty,
    types.updates.ChannelDifferenceTooLong,
    types.updates.ChannelDifference
))


class StateCache:
    """
    In-memory update state cache, defaultdict-like behaviour.
    """
    _store: dict

    def __init__(self, initial, loggers):
        # We only care about the pts and the date. By using a tuple which
        # is lightweight and immutable we can easily copy them around to
        # each update in case they need to fetch missing entities.
        self._logger = loggers[__name__]
        self._store = {}
        if initial:
            self._pts_date = initial.pts, initial.qts, initial.date
        else:
            self._pts_date = None, None, None

    def reset(self):
        self._store.clear()
        self._pts_date = None, None, None

    # TODO Call this when receiving responses too...?
    def update(
            self,
            update,
            *,
            channel_id=None,
            check_only=False
    ):
        """
        Update the state with the given update.
        """
        cid = update.CONSTRUCTOR_ID
        if check_only:
            return cid in has_pts or cid in has_date or cid in has_channel_pts

        new_pts_date = tuple()
        if cid in has_pts:
            new_pts_date += update.pts,
        else:
            new_pts_date += self._pts_date[0],
        if cid in has_qts:
            new_pts_date += update.qts,
        else:
            new_pts_date += self._pts_date[1],
        if cid in has_date:
            new_pts_date += update.date,
        else:
            new_pts_date += self._pts_date[2],
        self._pts_date = new_pts_date

        if cid in has_channel_pts:
            if channel_id is None:
                channel_id = self.get_channel_id(update)

            if channel_id is None:
                self._logger.info(
                    'Failed to retrieve channel_id from %s', update)
            else:
                self._store[channel_id] = update.pts

    def update_already_processed(self, update):
        cid = update.CONSTRUCTOR_ID
        # If pts == 0, the update is from catch_up
        if cid in has_pts and \
                update.pts != 0 and \
                update.pts >= self._pts_date[0]:
            return True
        if cid in has_qts and update.qts >= self._pts_date[1]:
            return True
        if cid in has_channel_pts:
            channel_id = self.get_channel_id(update)
            if update.pts != 0 and \
                    self._store.get(channel_id, 0) >= update.pts:
                return True
        return False

    def get_channel_id(
            self,
            update,
            has_channel_id=frozenset(_has_channel_id),
            # Hardcoded because only some with message are for channels
            has_message=frozenset(x.CONSTRUCTOR_ID for x in (
                    types.UpdateNewChannelMessage,
                    types.UpdateEditChannelMessage
            ))
    ):
        """
        Gets the **unmarked** channel ID from this update, if it has any.

        Fails for ``*difference`` updates, where ``channel_id``
        is supposedly already known from the outside.
        """
        cid = update.CONSTRUCTOR_ID
        if cid in has_channel_id:
            return update.channel_id
        elif cid in has_message:
            if update.message.peer_id is None:
                # Telegram sometimes sends empty messages to give a newer pts:
                # UpdateNewChannelMessage(message=MessageEmpty(id), pts=pts, pts_count=1)
                # Not sure why, but it's safe to ignore them.
                self._logger.debug('Update has None peer_id %s', update)
            else:
                return update.message.peer_id.channel_id

        return None

    def __getitem__(self, item):
        """
        If `item` is `None`, returns the default ``(pts, date)``.

        If it's an **unmarked** channel ID, returns its ``pts``.

        If no information is known, ``pts`` will be `None`.
        """
        if item is None:
            return self._pts_date
        else:
            return self._store.get(item)

    def __setitem__(self, where, value):
        if where is None:
            self._pts_date = value
        else:
            self._store[where] = value

    def get_channel_pts(self):
        return self._store
