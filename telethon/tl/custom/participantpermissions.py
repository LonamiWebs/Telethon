from .. import types


def _admin_prop(field_name, doc):
    """
    Helper method to build properties that return `True` if the user is an
    administrator of a normal chat, or otherwise return `True` if the user
    has a specific permission being an admin of a channel.
    """
    def fget(self):
        if not self.is_admin:
            return False
        if self.is_chat:
            return True

        return getattr(self.participant.admin_rights, field_name)

    return {'fget': fget, 'doc': doc}


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
    def has_left(self):
        """
        Whether the user left the chat.
        """
        return isinstance(self.participant, types.ChannelParticipantLeft)
    
    @property
    def add_admins(self):
        """
        Whether the administrator can add new administrators with the same or
        less permissions than them.
        """
        if not self.is_admin or (self.is_chat and not self.is_creator):
            return False

        return self.participant.admin_rights.add_admins

    ban_users = property(**_admin_prop('ban_users', """
        Whether the administrator can ban other users or not.
    """))

    pin_messages = property(**_admin_prop('pin_messages', """
        Whether the administrator can pin messages or not.
    """))

    invite_users = property(**_admin_prop('invite_users', """
        Whether the administrator can add new users to the chat.
    """))

    delete_messages = property(**_admin_prop('delete_messages', """
        Whether the administrator can delete messages from other participants.
    """))

    edit_messages = property(**_admin_prop('edit_messages', """
        Whether the administrator can edit messages.
    """))

    post_messages = property(**_admin_prop('post_messages', """
        Whether the administrator can post messages in the broadcast channel.
    """))

    change_info = property(**_admin_prop('change_info', """
        Whether the administrator can change the information about the chat,
        such as title or description.
    """))

    anonymous = property(**_admin_prop('anonymous', """
        Whether the administrator will remain anonymous when sending messages.
    """))
