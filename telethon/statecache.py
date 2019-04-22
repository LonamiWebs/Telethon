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
            has_pts=(
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
            ),
            has_date=(
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
            ),
            has_channel_pts=(
                types.UpdateChannelTooLong,
                types.UpdateNewChannelMessage,
                types.UpdateDeleteChannelMessages,
                types.UpdateEditChannelMessage,
                types.UpdateChannelWebPage,
                types.updates.ChannelDifferenceEmpty,
                types.updates.ChannelDifferenceTooLong,
                types.updates.ChannelDifference
            )
    ):
        """
        Update the state with the given update.
        """
        has_pts = isinstance(update, has_pts)
        has_date = isinstance(update, has_date)
        has_channel_pts = isinstance(update, has_channel_pts)
        if has_pts and has_date:
            self._pts_date = update.pts, update.date
        elif has_pts:
            self._pts_date = update.pts, self._pts_date[1]
        elif has_date:
            self._pts_date = self._pts_date[0], update.date

        if has_channel_pts:
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
            has_channel_id=(
                types.UpdateChannelTooLong,
                types.UpdateDeleteChannelMessages,
                types.UpdateChannelWebPage
            ),
            has_message=(
                types.UpdateNewChannelMessage,
                types.UpdateEditChannelMessage
            )
    ):
        # Will only fail for *difference, where channel_id is known
        if isinstance(update, has_channel_id):
            return update.channel_id
        elif isinstance(update, has_message):
            if update.message.to_id is None:
                self._logger.info('Update has None to_id %s', update)
            else:
                return update.message.to_id.channel_id

        return None

    def __getitem__(self, item):
        """
        Gets the corresponding ``(pts, date)`` for the given ID or peer,
        """
        if item is None:
            return self._pts_date
        else:
            return self.__dict__.get(item, 1)
