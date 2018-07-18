import datetime

from .common import EventBuilder, EventCommon, name_inner_event
from ..tl import types


@name_inner_event
class UserUpdate(EventBuilder):
    """
    Represents an user update (gone online, offline, joined Telegram).
    """
    @classmethod
    def build(cls, update):
        if isinstance(update, types.UpdateUserStatus):
            event = cls.Event(update.user_id,
                              status=update.status)
        else:
            return

        event._entities = update._entities
        return event

    class Event(EventCommon):
        """
        Represents the event of an user status update (last seen, joined).

        Members:
            online (`bool`, optional):
                ``True`` if the user is currently online, ``False`` otherwise.
                Might be ``None`` if this information is not present.

            last_seen (`datetime`, optional):
                Exact date when the user was last seen if known.

            until (`datetime`, optional):
                Until when will the user remain online.

            within_months (`bool`):
                ``True`` if the user was seen within 30 days.

            within_weeks (`bool`):
                ``True`` if the user was seen within 7 days.

            recently (`bool`):
                ``True`` if the user was seen within a day.

            action (:tl:`SendMessageAction`, optional):
                The "typing" action if any the user is performing if any.

            cancel (`bool`):
                ``True`` if the action was cancelling other actions.

            typing (`bool`):
                ``True`` if the action is typing a message.

            recording (`bool`):
                ``True`` if the action is recording something.

            uploading (`bool`):
                ``True`` if the action is uploading something.

            playing (`bool`):
                ``True`` if the action is playing a game.

            audio (`bool`):
                ``True`` if what's being recorded/uploaded is an audio.

            round (`bool`):
                ``True`` if what's being recorded/uploaded is a round video.

            video (`bool`):
                ``True`` if what's being recorded/uploaded is an video.

            document (`bool`):
                ``True`` if what's being uploaded is document.

            geo (`bool`):
                ``True`` if what's being uploaded is a geo.

            photo (`bool`):
                ``True`` if what's being uploaded is a photo.

            contact (`bool`):
                ``True`` if what's being uploaded (selected) is a contact.
        """
        def __init__(self, user_id, *, status=None, typing=None):
            super().__init__(types.PeerUser(user_id))

            self.online = None if status is None else \
                isinstance(status, types.UserStatusOnline)

            self.last_seen = status.was_online if \
                isinstance(status, types.UserStatusOffline) else None

            self.until = status.expires if \
                isinstance(status, types.UserStatusOnline) else None

            if self.last_seen:
                diff = datetime.datetime.now() - self.last_seen
                if diff < datetime.timedelta(days=30):
                    self.within_months = True
                    if diff < datetime.timedelta(days=7):
                        self.within_weeks = True
                        if diff < datetime.timedelta(days=1):
                            self.recently = True
            else:
                self.within_months = self.within_weeks = self.recently = False
                if isinstance(status, (types.UserStatusOnline,
                                       types.UserStatusRecently)):
                    self.within_months = self.within_weeks = True
                    self.recently = True
                elif isinstance(status, types.UserStatusLastWeek):
                    self.within_months = self.within_weeks = True
                elif isinstance(status, types.UserStatusLastMonth):
                    self.within_months = True

            self.action = typing
            if typing:
                self.cancel = self.typing = self.recording = self.uploading = \
                    self.playing = False
                self.audio = self.round = self.video = self.document = \
                    self.geo = self.photo = self.contact = False

                if isinstance(typing, types.SendMessageCancelAction):
                    self.cancel = True
                elif isinstance(typing, types.SendMessageTypingAction):
                    self.typing = True
                elif isinstance(typing, types.SendMessageGamePlayAction):
                    self.playing = True
                elif isinstance(typing, types.SendMessageGeoLocationAction):
                    self.geo = True
                elif isinstance(typing, types.SendMessageRecordAudioAction):
                    self.recording = self.audio = True
                elif isinstance(typing, types.SendMessageRecordRoundAction):
                    self.recording = self.round = True
                elif isinstance(typing, types.SendMessageRecordVideoAction):
                    self.recording = self.video = True
                elif isinstance(typing, types.SendMessageChooseContactAction):
                    self.uploading = self.contact = True
                elif isinstance(typing, types.SendMessageUploadAudioAction):
                    self.uploading = self.audio = True
                elif isinstance(typing, types.SendMessageUploadDocumentAction):
                    self.uploading = self.document = True
                elif isinstance(typing, types.SendMessageUploadPhotoAction):
                    self.uploading = self.photo = True
                elif isinstance(typing, types.SendMessageUploadRoundAction):
                    self.uploading = self.round = True
                elif isinstance(typing, types.SendMessageUploadVideoAction):
                    self.uploading = self.video = True

        @property
        def user(self):
            """Alias for `chat` (conversation)."""
            return self.chat

        async def get_user(self):
            """Alias for `get_chat` (conversation)."""
            return await self.get_chat()

        @property
        def input_user(self):
            """Alias for `input_chat`."""
            return self.input_chat

        async def get_input_user(self):
            """Alias for `get_input_chat`."""
            return await self.get_input_chat()

        @property
        def user_id(self):
            """Alias for `chat_id`."""
            return self.chat_id
