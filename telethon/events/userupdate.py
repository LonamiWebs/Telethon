import datetime
import functools

from .common import EventBuilder, EventCommon, name_inner_event
from .. import utils
from ..tl import types
from ..tl.custom.sendergetter import SenderGetter


# TODO Either the properties are poorly named or they should be
#      different events, but that would be a breaking change.
#
# TODO There are more "user updates", but bundling them all up
#      in a single place will make it annoying to use (since
#      the user needs to check for the existence of `None`).
#
# TODO Handle UpdateUserBlocked, UpdateUserName, UpdateUserPhone, UpdateUser

def _requires_action(function):
    @functools.wraps(function)
    def wrapped(self):
        return None if self.action is None else function(self)

    return wrapped


def _requires_status(function):
    @functools.wraps(function)
    def wrapped(self):
        return None if self.status is None else function(self)

    return wrapped


@name_inner_event
class UserUpdate(EventBuilder):
    """
    Occurs whenever a user goes online, starts typing, etc.

    Example
        .. code-block:: python

            from telethon import events

            @client.on(events.UserUpdate)
            async def handler(event):
                # If someone is uploading, say something
                if event.uploading:
                    await client.send_message(event.user_id, 'What are you sending?')
    """
    @classmethod
    def build(cls, update, others=None, self_id=None):
        if isinstance(update, types.UpdateUserStatus):
            return cls.Event(types.PeerUser(update.user_id),
                             status=update.status)
        elif isinstance(update, types.UpdateChannelUserTyping):
            return cls.Event(update.from_id,
                             chat_peer=types.PeerChannel(update.channel_id),
                             typing=update.action)
        elif isinstance(update, types.UpdateChatUserTyping):
            return cls.Event(update.from_id,
                             chat_peer=types.PeerChat(update.chat_id),
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
                of the seen within properties, since they will all be `None`
                if the status is not set.

            action (:tl:`SendMessageAction`, optional):
                The "typing" action if any the user is performing if any.

                You should check this attribute first before checking any
                of the typing properties, since they will all be `None`
                if the action is not set.
        """
        def __init__(self, peer, *, status=None, chat_peer=None, typing=None):
            super().__init__(chat_peer or peer)
            SenderGetter.__init__(self, utils.get_peer_id(peer))

            self.status = status
            self.action = typing

        def _set_client(self, client):
            super()._set_client(client)
            self._sender, self._input_sender = utils._get_entity_pair(
                self.sender_id, self._entities, client._mb_entity_cache)

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
        @_requires_action
        def typing(self):
            """
            `True` if the action is typing a message.
            """
            return isinstance(self.action, types.SendMessageTypingAction)

        @property
        @_requires_action
        def uploading(self):
            """
            `True` if the action is uploading something.
            """
            return isinstance(self.action, (
                types.SendMessageChooseContactAction,
                types.SendMessageChooseStickerAction,
                types.SendMessageUploadAudioAction,
                types.SendMessageUploadDocumentAction,
                types.SendMessageUploadPhotoAction,
                types.SendMessageUploadRoundAction,
                types.SendMessageUploadVideoAction
            ))

        @property
        @_requires_action
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
        @_requires_action
        def playing(self):
            """
            `True` if the action is playing a game.
            """
            return isinstance(self.action, types.SendMessageGamePlayAction)

        @property
        @_requires_action
        def cancel(self):
            """
            `True` if the action was cancelling other actions.
            """
            return isinstance(self.action, types.SendMessageCancelAction)

        @property
        @_requires_action
        def geo(self):
            """
            `True` if what's being uploaded is a geo.
            """
            return isinstance(self.action, types.SendMessageGeoLocationAction)

        @property
        @_requires_action
        def audio(self):
            """
            `True` if what's being recorded/uploaded is an audio.
            """
            return isinstance(self.action, (
                types.SendMessageRecordAudioAction,
                types.SendMessageUploadAudioAction
            ))

        @property
        @_requires_action
        def round(self):
            """
            `True` if what's being recorded/uploaded is a round video.
            """
            return isinstance(self.action, (
                types.SendMessageRecordRoundAction,
                types.SendMessageUploadRoundAction
            ))

        @property
        @_requires_action
        def video(self):
            """
            `True` if what's being recorded/uploaded is an video.
            """
            return isinstance(self.action, (
                types.SendMessageRecordVideoAction,
                types.SendMessageUploadVideoAction
            ))

        @property
        @_requires_action
        def contact(self):
            """
            `True` if what's being uploaded (selected) is a contact.
            """
            return isinstance(self.action, types.SendMessageChooseContactAction)

        @property
        @_requires_action
        def document(self):
            """
            `True` if what's being uploaded is document.
            """
            return isinstance(self.action, types.SendMessageUploadDocumentAction)

        @property
        @_requires_action
        def sticker(self):
            """
            `True` if what's being uploaded is a sticker.
            """
            return isinstance(self.action, types.SendMessageChooseStickerAction)

        @property
        @_requires_action
        def photo(self):
            """
            `True` if what's being uploaded is a photo.
            """
            return isinstance(self.action, types.SendMessageUploadPhotoAction)

        @property
        @_requires_status
        def last_seen(self):
            """
            Exact `datetime.datetime` when the user was last seen if known.
            """
            if isinstance(self.status, types.UserStatusOffline):
                return self.status.was_online

        @property
        @_requires_status
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
            else:
                return datetime.timedelta(days=365)

        @property
        @_requires_status
        def online(self):
            """
            `True` if the user is currently online,
            """
            return self._last_seen_delta() <= datetime.timedelta(days=0)

        @property
        @_requires_status
        def recently(self):
            """
            `True` if the user was seen within a day.
            """
            return self._last_seen_delta() <= datetime.timedelta(days=1)

        @property
        @_requires_status
        def within_weeks(self):
            """
            `True` if the user was seen within 7 days.
            """
            return self._last_seen_delta() <= datetime.timedelta(days=7)

        @property
        @_requires_status
        def within_months(self):
            """
            `True` if the user was seen within 30 days.
            """
            return self._last_seen_delta() <= datetime.timedelta(days=30)
