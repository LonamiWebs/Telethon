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
        return self.is_creator or isinstance(self.participant, (
            types.ChannelParticipantAdmin,
            types.ChatParticipantAdmin
        ))

    @property
    def is_creator(self):
        return isinstance(self.participant, (
            types.ChannelParticipantCreator,
            types.ChatParticipantCreator
        ))

    @property
    def has_default_permissions(self):
        return isinstance(self.participant, (
            types.ChannelParticipant,
            types.ChatParticipant,
            types.ChannelParticipantSelf
        ))

    @property
    def is_banned(self):
        return isinstance(self.participant, types.ChannelParticipantBanned)

    @property
    def ban_users(self):
        if not self.is_admin:
            return False
        if self.is_chat:
            return True
        return self.participant.admin_rights.ban_users

    @property
    def pin_messages(self):
        if not self.is_admin:
            return False
        if self.is_chat:
            return True
        return self.participant.admin_rights.pin_messages

    @property
    def add_admins(self):
        if not self.is_admin:
            return False
        if self.is_chat and not self.is_creator:
            return False
        return self.participant.admin_rights.add_admins

    @property
    def invite_users(self):
        if not self.is_admin:
            return False
        if self.is_chat:
            return True
        return self.participant.admin_rights.invite_users

    @property
    def delete_messages(self):
        if not self.is_admin:
            return False
        if self.is_chat:
            return True
        return self.participant.admin_rights.delete_messages

    @property
    def edit_messages(self):
        if not self.is_admin:
            return False
        if self.is_chat:
            return True
        return self.participant.admin_rights.edit_messages

    @property
    def post_messages(self):
        if not self.is_admin:
            return False
        if self.is_chat:
            return True
        return self.participant.admin_rights.post_messages

    @property
    def change_info(self):
        if not self.is_admin:
            return False
        if self.is_chat:
            return True
        return self.participant.admin_rights.change_info
