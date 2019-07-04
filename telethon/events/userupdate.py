import datetime

from .common import EventBuilder, EventCommon, name_inner_event
from .. import utils
from ..tl import types
from ..tl.custom.sendergetter import SenderGetter


# TODO Either the properties are poorly named or they should be
#      different events, but that would be a breaking change.

@name_inner_event
class UserUpdate(EventBuilder):
    """
    Occurs whenever a user goes online, starts typing, etc.
    """
    @classmethod
    def build(cls, update, others=None):
        if isinstance(update, types.UpdateUserStatus):
            return cls.Event(update.user_id,
                             status=update.status)
        elif isinstance(update, types.UpdateChatUserTyping):
            # Unfortunately, we can't know whether `chat_id`'s type
            return cls.Event(update.user_id,
                             chat_id=update.chat_id,
                             typing=update.action)
        elif isinstance(update, types.UpdateUserTyping):
            return cls.Event(update.user_id,
                             typing=update.action)

    class Event(EventCommon, SenderGetter):
        """
        Represents the event of a user update
        such as gone online, started typing, etc.

        Members:
            status (:tl:`UserStatus`, optional):
                The user status if the update is about going online or offline.

                You should check this attribute first before checking any
                of the seen within properties, since they will all be `False`
                if the status is not set.

            action (:tl:`SendMessageAction`, optional):
                The "typing" action if any the user is performing if any.

                You should check this attribute first before checking any
                of the typing properties, since they will all be `False`
                if the action is not set.
        """
        def __init__(self, user_id, *, status=None, chat_id=None, typing=None):
            if chat_id is None:
                super().__init__(types.PeerUser(user_id))
            else:
                # Temporarily set the chat_peer to the ID until ._set_client.
                # We need the client to actually figure out its type.
                super().__init__(chat_id)

            SenderGetter.__init__(self, user_id)

            self.status = status
            self.action = typing

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

        @property
        def typing(self):
            """
            `True` if the action is typing a message.
            """
            return isinstance(self.action, types.SendMessageTypingAction)

        @property
        def uploading(self):
            """
            `True` if the action is uploading something.
            """
            return isinstance(self.action, (
                types.SendMessageChooseContactAction,
                types.SendMessageUploadAudioAction,
                types.SendMessageUploadDocumentAction,
                types.SendMessageUploadPhotoAction,
                types.SendMessageUploadRoundAction,
                types.SendMessageUploadVideoAction
            ))

        @property
        def recording(self):
            """
            `True` if the action is recording something.
            """
            return isinstance(self.action, (
                types.SendMessageRecordAudioAction,
                types.SendMessageRecordRoundAction,
                types.SendMessageRecordVideoAction
            ))

        @property
        def playing(self):
            """
            `True` if the action is playing a game.
            """
            return isinstance(self.action, types.SendMessageGamePlayAction)

        @property
        def cancel(self):
            """
            `True` if the action was cancelling other actions.
            """
            return isinstance(self.action, types.SendMessageCancelAction)

        @property
        def geo(self):
            """
            `True` if what's being uploaded is a geo.
            """
            return isinstance(self.action, types.SendMessageGeoLocationAction)

        @property
        def audio(self):
            """
            `True` if what's being recorded/uploaded is an audio.
            """
            return isinstance(self.action, (
                types.SendMessageRecordAudioAction,
                types.SendMessageUploadAudioAction
            ))

        @property
        def round(self):
            """
            `True` if what's being recorded/uploaded is a round video.
            """
            return isinstance(self.action, (
                types.SendMessageRecordRoundAction,
                types.SendMessageUploadRoundAction
            ))

        @property
        def video(self):
            """
            `True` if what's being recorded/uploaded is an video.
            """
            return isinstance(self.action, (
                types.SendMessageRecordVideoAction,
                types.SendMessageUploadVideoAction
            ))

        @property
        def contact(self):
            """
            `True` if what's being uploaded (selected) is a contact.
            """
            return isinstance(self.action, types.SendMessageChooseContactAction)

        @property
        def document(self):
            """
            `True` if what's being uploaded is document.
            """
            return isinstance(self.action, types.SendMessageUploadDocumentAction)

        @property
        def photo(self):
            """
            `True` if what's being uploaded is a photo.
            """
            return isinstance(self.action, types.SendMessageUploadPhotoAction)

        @property
        def last_seen(self):
            """
            Exact `datetime.datetime` when the user was last seen if known.
            """
            if isinstance(self.status, types.UserStatusOffline):
                return self.status.was_online

        @property
        def until(self):
            """
            The `datetime.datetime` until when the user should appear online.
            """
            if isinstance(self.status, types.UserStatusOnline):
                return self.status.expires

        def _last_seen_delta(self):
            if isinstance(self.status, types.UserStatusOffline):
                return datetime.datetime.now(tz=datetime.timezone.utc) - self.status.was_online
            elif isinstance(self.status, types.UserStatusOnline):
                return datetime.timedelta(days=0)
            elif isinstance(self.status, types.UserStatusRecently):
                return datetime.timedelta(days=1)
            elif isinstance(self.status, types.UserStatusLastWeek):
                return datetime.timedelta(days=7)
            elif isinstance(self.status, types.UserStatusLastMonth):
                return datetime.timedelta(days=30)

        @property
        def online(self):
            """
            `True` if the user is currently online,
            """
            return self._last_seen_delta() <= datetime.timedelta(days=0)

        @property
        def recently(self):
            """
            `True` if the user was seen within a day.
            """
            return self._last_seen_delta() <= datetime.timedelta(days=1)

        @property
        def within_weeks(self):
            """
            `True` if the user was seen within 7 days.
            """
            return self._last_seen_delta() <= datetime.timedelta(days=7)

        @property
        def within_months(self):
            """
            `True` if the user was seen within 30 days.
            """
            return self._last_seen_delta() <= datetime.timedelta(days=30)
