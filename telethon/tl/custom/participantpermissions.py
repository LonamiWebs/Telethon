from .. import types


class ParticipantPermissions:
    """
    Participant permissions information.

    The properties in this objects are boolean values indicating whether the
    user has the permission or not.

    Example
        .. code-block:: python

            permissions = ...

            if permissions.is_banned:
                "this user is banned"
            elif permissions.is_admin:
                "this user is an administrator"
    """
    def __init__(self, participant, chat: bool):
        self.participant = participant
        self.is_chat = chat

    @property
    def is_admin(self):
        """
        Whether the user is an administrator of the chat or not. The creator
        also counts as begin an administrator, since they have all permissions.
        """
        return self.is_creator or isinstance(self.participant, (
            types.ChannelParticipantAdmin,
            types.ChatParticipantAdmin
        ))

    @property
    def is_creator(self):
        """
        Whether the user is the creator of the chat or not.
        """
        return isinstance(self.participant, (
            types.ChannelParticipantCreator,
            types.ChatParticipantCreator
        ))

    @property
    def has_default_permissions(self):
        """
        Whether the user is a normal user of the chat (not administrator, but
        not banned either, and has no restrictions applied).
        """
        return isinstance(self.participant, (
            types.ChannelParticipant,
            types.ChatParticipant,
            types.ChannelParticipantSelf
        ))

    @property
    def is_banned(self):
        """
        Whether the user is banned in the chat.
        """
        return isinstance(self.participant, types.ChannelParticipantBanned)

    @property
    def ban_users(self):
        """
        Whether the administrator can ban other users or not.
        """
        if not self.is_admin:
            return False
        if self.is_chat:
            return True
        return self.participant.admin_rights.ban_users

    @property
    def pin_messages(self):
        """
        Whether the administrator can pin messages or not.
        """
        if not self.is_admin:
            return False
        if self.is_chat:
            return True
        return self.participant.admin_rights.pin_messages

    @property
    def add_admins(self):
        """
        Whether the administrator can add new administrators with the same or
        less permissions than them.
        """
        if not self.is_admin:
            return False
        if self.is_chat and not self.is_creator:
            return False
        return self.participant.admin_rights.add_admins

    @property
    def invite_users(self):
        """
        Whether the administrator can add new users to the chat.
        """
        if not self.is_admin:
            return False
        if self.is_chat:
            return True
        return self.participant.admin_rights.invite_users

    @property
    def delete_messages(self):
        """
        Whether the administrator can delete messages from other participants.
        """
        if not self.is_admin:
            return False
        if self.is_chat:
            return True
        return self.participant.admin_rights.delete_messages

    @property
    def edit_messages(self):
        """
        Whether the administrator can edit messages.
        """
        if not self.is_admin:
            return False
        if self.is_chat:
            return True
        return self.participant.admin_rights.edit_messages

    @property
    def post_messages(self):
        """
        Whether the administrator can post messages in the broadcast channel.
        """
        if not self.is_admin:
            return False
        if self.is_chat:
            return True
        return self.participant.admin_rights.post_messages

    @property
    def change_info(self):
        """
        Whether the administrator can change the information about the chat,
        such as title or description.
        """
        if not self.is_admin:
            return False
        if self.is_chat:
            return True
        return self.participant.admin_rights.change_info

    @property
    def anonymous(self):
        """
        Whether the administrator will remain anonymous when sending messages.
        """
        if not self.is_admin:
            return False
        if self.is_chat:
            return True
        return self.participant.admin_rights.anonymous
