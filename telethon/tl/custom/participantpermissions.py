from .. import types


class ParticipantPermissions:
    """
    Participant permissions information
    """
    def __init__(self, participant):
        self.participant = participant

    @property
    def is_admin(self):
        return self.is_creator or isinstance(self.participant, types.ChannelParticipantAdmin)

    @property
    def is_creator(self):
        return isinstance(self.participant, types.ChannelParticipantCreator)

    @property
    def is_default_permissions(self):
        return isinstance(self.participant, types.ChannelParticipant)

    @property
    def is_banned(self):
        return isinstance(self.participant, types.ChannelParticipantBanned)

    @property
    def is_self(self):
        return isinstance(self.participant, types.ChannelParticipantSelf)
