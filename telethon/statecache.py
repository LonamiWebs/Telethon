import datetime

from .tl import types


class StateCache:
    """
    In-memory update state cache, defaultdict-like behaviour.
    """
    def __init__(self, initial, loggers):
        # We only care about the pts and the date. By using a tuple which
        # is lightweight and immutable we can easily copy them around to
        # each update in case they need to fetch missing entities.
        self._logger = loggers[__name__]
        if initial:
            self._pts_date = initial.pts, initial.date
        else:
            self._pts_date = 1, datetime.datetime.now()

    def reset(self):
        self.__dict__.clear()
        self._pts_date = (1, 1)

    # TODO Call this when receiving responses too...?
    def update(
            self,
            update,
            *,
            channel_id=None,
            has_pts=frozenset(x.CONSTRUCTOR_ID for x in (
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
            )),
            has_date=frozenset(x.CONSTRUCTOR_ID for x in (
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
            )),
            has_channel_pts=frozenset(x.CONSTRUCTOR_ID for x in (
                types.UpdateChannelTooLong,
                types.UpdateNewChannelMessage,
                types.UpdateDeleteChannelMessages,
                types.UpdateEditChannelMessage,
                types.UpdateChannelWebPage,
                types.updates.ChannelDifferenceEmpty,
                types.updates.ChannelDifferenceTooLong,
                types.updates.ChannelDifference
            ))
    ):
        """
        Update the state with the given update.
        """
        cid = update.CONSTRUCTOR_ID
        if cid in has_pts:
            if cid in has_date:
                self._pts_date = update.pts, update.date
            else:
                self._pts_date = update.pts, self._pts_date[1]
        elif cid in has_date:
            self._pts_date = self._pts_date[0], update.date

        if cid in has_channel_pts:
            if channel_id is None:
                channel_id = self.get_channel_id(update)

            if channel_id is None:
                self._logger.info(
                    'Failed to retrieve channel_id from %s', update)
            else:
                self.__dict__[channel_id] = update.pts

    def get_channel_id(
            self,
            update,
            has_channel_id=frozenset(x.CONSTRUCTOR_ID for x in (
                types.UpdateChannelTooLong,
                types.UpdateDeleteChannelMessages,
                types.UpdateChannelWebPage
            )),
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
            if update.message.to_id is None:
                self._logger.info('Update has None to_id %s', update)
            else:
                return update.message.to_id.channel_id

        return None

    def __getitem__(self, item):
        """
        If `item` is ``None``, returns the default ``(pts, date)``.

        If it's an **unmarked** channel ID, returns its ``pts``.
        """
        if item is None:
            return self._pts_date
        else:
            return self.__dict__.get(item, 1)
