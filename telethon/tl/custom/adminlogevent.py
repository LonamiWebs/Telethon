from ...tl import types
from ...utils import get_input_peer


class AdminLogEvent:
    """
    Represents a more friendly interface for admin log events.

    Members:
        original (:tl:`ChannelAdminLogEvent`):
            The original :tl:`ChannelAdminLogEvent`.

        entities (`dict`):
            A dictionary mapping user IDs to :tl:`User`.

            When `old` and `new` are :tl:`ChannelParticipant`, you can
            use this dictionary to map the ``user_id``, ``kicked_by``,
            ``inviter_id`` and ``promoted_by`` IDs to their :tl:`User`.

        user (:tl:`User`):
            The user that caused this action (``entities[original.user_id]``).

        input_user (:tl:`InputPeerUser`):
            Input variant of `user`.
    """
    def __init__(self, original, entities):
        self.original = original
        self.entities = entities
        self.user = entities[original.user_id]
        self.input_user = get_input_peer(self.user)

    @property
    def id(self):
        """
        The ID of this event.
        """
        return self.original.id

    @property
    def date(self):
        """
        The date when this event occurred.
        """
        return self.original.date

    @property
    def user_id(self):
        """
        The ID of the user that triggered this event.
        """
        return self.original.user_id

    @property
    def action(self):
        """
        The original :tl:`ChannelAdminLogEventAction`.
        """
        return self.original.action

    @property
    def old(self):
        """
        The old value from the event.
        """
        ori = self.original.action
        if isinstance(ori, (
                types.ChannelAdminLogEventActionChangeAbout,
                types.ChannelAdminLogEventActionChangeTitle,
                types.ChannelAdminLogEventActionChangeUsername,
                types.ChannelAdminLogEventActionChangeLocation
        )):
            return ori.prev_value
        elif isinstance(ori, types.ChannelAdminLogEventActionChangePhoto):
            return ori.prev_photo
        elif isinstance(ori, types.ChannelAdminLogEventActionChangeStickerSet):
            return ori.prev_stickerset
        elif isinstance(ori, types.ChannelAdminLogEventActionEditMessage):
            return ori.prev_message
        elif isinstance(ori, (
                types.ChannelAdminLogEventActionParticipantToggleAdmin,
                types.ChannelAdminLogEventActionParticipantToggleBan
        )):
            return ori.prev_participant
        elif isinstance(ori, (
                types.ChannelAdminLogEventActionToggleInvites,
                types.ChannelAdminLogEventActionTogglePreHistoryHidden,
                types.ChannelAdminLogEventActionToggleSignatures
        )):
            return not ori.new_value
        elif isinstance(ori, types.ChannelAdminLogEventActionDeleteMessage):
            return ori.message
        elif isinstance(ori, types.ChannelAdminLogEventActionDefaultBannedRights):
            return ori.prev_banned_rights

    @property
    def new(self):
        """
        The new value present in the event.
        """
        ori = self.original.action
        if isinstance(ori, (
                types.ChannelAdminLogEventActionChangeAbout,
                types.ChannelAdminLogEventActionChangeTitle,
                types.ChannelAdminLogEventActionChangeUsername,
                types.ChannelAdminLogEventActionToggleInvites,
                types.ChannelAdminLogEventActionTogglePreHistoryHidden,
                types.ChannelAdminLogEventActionToggleSignatures,
                types.ChannelAdminLogEventActionChangeLocation
        )):
            return ori.new_value
        elif isinstance(ori, types.ChannelAdminLogEventActionChangePhoto):
            return ori.new_photo
        elif isinstance(ori, types.ChannelAdminLogEventActionChangeStickerSet):
            return ori.new_stickerset
        elif isinstance(ori, types.ChannelAdminLogEventActionEditMessage):
            return ori.new_message
        elif isinstance(ori, (
                types.ChannelAdminLogEventActionParticipantToggleAdmin,
                types.ChannelAdminLogEventActionParticipantToggleBan
        )):
            return ori.new_participant
        elif isinstance(ori, types.ChannelAdminLogEventActionParticipantInvite):
            return ori.participant
        elif isinstance(ori, types.ChannelAdminLogEventActionDefaultBannedRights):
            return ori.new_banned_rights
        elif isinstance(ori, types.ChannelAdminLogEventActionStopPoll):
            return ori.message

    @property
    def changed_about(self):
        """
        Whether the channel's about was changed or not.

        If `True`, `old` and `new` will be present as `str`.
        """
        return isinstance(self.original.action,
                          types.ChannelAdminLogEventActionChangeAbout)

    @property
    def changed_title(self):
        """
        Whether the channel's title was changed or not.

        If `True`, `old` and `new` will be present as `str`.
        """
        return isinstance(self.original.action,
                          types.ChannelAdminLogEventActionChangeTitle)

    @property
    def changed_username(self):
        """
        Whether the channel's username was changed or not.

        If `True`, `old` and `new` will be present as `str`.
        """
        return isinstance(self.original.action,
                          types.ChannelAdminLogEventActionChangeUsername)

    @property
    def changed_photo(self):
        """
        Whether the channel's photo was changed or not.

        If `True`, `old` and `new` will be present as :tl:`Photo`.
        """
        return isinstance(self.original.action,
                          types.ChannelAdminLogEventActionChangePhoto)

    @property
    def changed_sticker_set(self):
        """
        Whether the channel's sticker set was changed or not.

        If `True`, `old` and `new` will be present as :tl:`InputStickerSet`.
        """
        return isinstance(self.original.action,
                          types.ChannelAdminLogEventActionChangeStickerSet)

    @property
    def changed_message(self):
        """
        Whether a message in this channel was edited or not.

        If `True`, `old` and `new` will be present as
        `Message <telethon.tl.custom.message.Message>`.
        """
        return isinstance(self.original.action,
                          types.ChannelAdminLogEventActionEditMessage)

    @property
    def deleted_message(self):
        """
        Whether a message in this channel was deleted or not.

        If `True`, `old` will be present as
        `Message <telethon.tl.custom.message.Message>`.
        """
        return isinstance(self.original.action,
                          types.ChannelAdminLogEventActionDeleteMessage)

    @property
    def changed_admin(self):
        """
        Whether the permissions for an admin in this channel
        changed or not.

        If `True`, `old` and `new` will be present as
        :tl:`ChannelParticipant`.
        """
        return isinstance(
            self.original.action,
            types.ChannelAdminLogEventActionParticipantToggleAdmin)

    @property
    def changed_restrictions(self):
        """
        Whether a message in this channel was edited or not.

        If `True`, `old` and `new` will be present as
        :tl:`ChannelParticipant`.
        """
        return isinstance(
            self.original.action,
            types.ChannelAdminLogEventActionParticipantToggleBan)

    @property
    def changed_invites(self):
        """
        Whether the invites in the channel were toggled or not.

        If `True`, `old` and `new` will be present as `bool`.
        """
        return isinstance(self.original.action,
                          types.ChannelAdminLogEventActionToggleInvites)

    @property
    def changed_location(self):
        """
        Whether the location setting of the channel has changed or not.

        If `True`, `old` and `new` will be present as :tl:`ChannelLocation`.
        """
        return isinstance(self.original.action,
                          types.ChannelAdminLogEventActionChangeLocation)

    @property
    def joined(self):
        """
        Whether `user` joined through the channel's
        public username or not.
        """
        return isinstance(self.original.action,
                          types.ChannelAdminLogEventActionParticipantJoin)

    @property
    def joined_invite(self):
        """
        Whether a new user joined through an invite
        link to the channel or not.

        If `True`, `new` will be present as
        :tl:`ChannelParticipant`.
        """
        return isinstance(self.original.action,
                          types.ChannelAdminLogEventActionParticipantInvite)

    @property
    def left(self):
        """
        Whether `user` left the channel or not.
        """
        return isinstance(self.original.action,
                          types.ChannelAdminLogEventActionParticipantLeave)

    @property
    def changed_hide_history(self):
        """
        Whether hiding the previous message history for new members
        in the channel was toggled or not.

        If `True`, `old` and `new` will be present as `bool`.
        """
        return isinstance(self.original.action,
                          types.ChannelAdminLogEventActionTogglePreHistoryHidden)

    @property
    def changed_signatures(self):
        """
        Whether the message signatures in the channel were toggled
        or not.

        If `True`, `old` and `new` will be present as `bool`.
        """
        return isinstance(self.original.action,
                          types.ChannelAdminLogEventActionToggleSignatures)

    @property
    def changed_pin(self):
        """
        Whether a new message in this channel was pinned or not.

        If `True`, `new` will be present as
        `Message <telethon.tl.custom.message.Message>`.
        """
        return isinstance(self.original.action,
                          types.ChannelAdminLogEventActionUpdatePinned)

    @property
    def changed_default_banned_rights(self):
        """
        Whether the default banned rights were changed or not.

        If `True`, `old` and `new` will
        be present as :tl:`ChatBannedRights`.
        """
        return isinstance(self.original.action,
                          types.ChannelAdminLogEventActionDefaultBannedRights)

    @property
    def stopped_poll(self):
        """
        Whether a poll was stopped or not.

        If `True`, `new` will be present as
        `Message <telethon.tl.custom.message.Message>`.
        """
        return isinstance(self.original.action,
                          types.ChannelAdminLogEventActionStopPoll)

    def __str__(self):
        return str(self.original)

    def stringify(self):
        return self.original.stringify()
