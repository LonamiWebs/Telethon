import datetime

from .common import EventBuilder, EventCommon, name_inner_event
from .. import utils
from ..tl import types
from ..tl.custom.sendergetter import SenderGetter


@name_inner_event
class UserUpdate(EventBuilder):
    """
    Occurs whenever a user goes online, starts typing, etc.
    """
    @classmethod
    def build(cls, update):
        if isinstance(update, types.UpdateUserStatus):
            event = cls.Event(update.user_id,
                              status=update.status)
        elif isinstance(update, types.UpdateChatUserTyping):
            # Unfortunately, we can't know whether `chat_id`'s type
            event = cls.Event(update.user_id,
                              chat_id=update.chat_id,
                              typing=update.action)
        elif isinstance(update, types.UpdateUserTyping):
            event = cls.Event(update.user_id,
                              typing=update.action)
        else:
            return

        event._entities = update._entities
        return event

    class Event(EventCommon, SenderGetter):
        """
        Represents the event of a user update
        such as gone online, started typing, etc.

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
        def __init__(self, user_id, *, status=None, chat_id=None, typing=None):
            if chat_id is None:
                super().__init__(types.PeerUser(user_id))
            else:
                # Temporarily set the chat_peer to the ID until ._set_client.
                # We need the client to actually figure out its type.
                super().__init__(chat_id)

            SenderGetter.__init__(self, user_id)

            self.online = None if status is None else \
                isinstance(status, types.UserStatusOnline)

            self.last_seen = status.was_online if \
                isinstance(status, types.UserStatusOffline) else None

            self.until = status.expires if \
                isinstance(status, types.UserStatusOnline) else None

            if self.last_seen:
                now = datetime.datetime.now(tz=datetime.timezone.utc)
                diff = now - self.last_seen
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

        def _set_client(self, client):
            if isinstance(self._chat_peer, int):
                try:
                    chat = client._entity_cache[self._chat_peer]
                    if isinstance(chat, types.InputPeerChat):
                        self._chat_peer = types.PeerChat(self._chat_peer)
                    elif isinstance(chat, types.InputPeerChannel):
                        self._chat_peer = types.PeerChannel(self._chat_peer)
                    else:
                        # Should not happen
                        self._chat_peer = types.PeerUser(self._chat_peer)
                except KeyError:
                    # Hope for the best. We don't know where this event
                    # occurred but it was most likely in a channel.
                    self._chat_peer = types.PeerChannel(self._chat_peer)

            super()._set_client(client)
            self._sender, self._input_sender = utils._get_entity_pair(
                self.sender_id, self._entities, client._entity_cache)

        @property
        def user(self):
            """Alias for `sender <telethon.tl.custom.sendergetter.SenderGetter.sender>`."""
            return self.sender

        async def get_user(self):
            """Alias for `get_sender <telethon.tl.custom.sendergetter.SenderGetter.get_sender>`."""
            return await self.get_sender()

        @property
        def input_user(self):
            """Alias for `input_sender <telethon.tl.custom.sendergetter.SenderGetter.input_sender>`."""
            return self.input_sender

        async def get_input_user(self):
            """Alias for `get_input_sender <telethon.tl.custom.sendergetter.SenderGetter.get_input_sender>`."""
            return await self.get_input_sender()

        @property
        def user_id(self):
            """Alias for `sender_id <telethon.tl.custom.sendergetter.SenderGetter.sender_id>`."""
            return self.sender_id
