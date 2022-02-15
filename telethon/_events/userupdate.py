import datetime
import functools

from .base import EventBuilder
from .._misc import utils
from .. import _tl
from ..types import _custom


# TODO Either the properties are poorly named or they should be
#      different events, but that would be a breaking change.
#
# TODO There are more "user updates", but bundling them all up
#      in a single place will make it annoying to use (since
#      the user needs to check for the existence of `None`).
#
# TODO Handle UpdateUserBlocked, UpdateUserName, UpdateUserPhone, UpdateUserPhoto

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


class UserUpdate(EventBuilder, _custom.chatgetter.ChatGetter, _custom.sendergetter.SenderGetter):
    """
    Occurs whenever a user goes online, starts typing, etc.

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
    def _build(cls, client, update, entities):
        chat_peer = None
        status = None
        if isinstance(update, _tl.UpdateUserStatus):
            peer = _tl.PeerUser(update.user_id)
            status = update.status
            typing = None
        elif isinstance(update, _tl.UpdateChannelUserTyping):
            peer = update.from_id
            chat_peer = _tl.PeerChannel(update.channel_id)
            typing = update.action
        elif isinstance(update, _tl.UpdateChatUserTyping):
            peer = update.from_id
            chat_peer = _tl.PeerChat(update.chat_id)
            typing = update.action
        elif isinstance(update, _tl.UpdateUserTyping):
            peer = update.user_id
            typing = update.action
        else:
            return None

        self = cls.__new__(cls)
        self._client = client
        self._sender = entities.get(peer)
        self._chat = entities.get(chat_peer or peer)
        self.status = status
        self.action = typing
        return self

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
        return isinstance(self.action, _tl.SendMessageTypingAction)

    @property
    @_requires_action
    def uploading(self):
        """
        `True` if the action is uploading something.
        """
        return isinstance(self.action, (
            _tl.SendMessageChooseContactAction,
            _tl.SendMessageChooseStickerAction,
            _tl.SendMessageUploadAudioAction,
            _tl.SendMessageUploadDocumentAction,
            _tl.SendMessageUploadPhotoAction,
            _tl.SendMessageUploadRoundAction,
            _tl.SendMessageUploadVideoAction
        ))

    @property
    @_requires_action
    def recording(self):
        """
        `True` if the action is recording something.
        """
        return isinstance(self.action, (
            _tl.SendMessageRecordAudioAction,
            _tl.SendMessageRecordRoundAction,
            _tl.SendMessageRecordVideoAction
        ))

    @property
    @_requires_action
    def playing(self):
        """
        `True` if the action is playing a game.
        """
        return isinstance(self.action, _tl.SendMessageGamePlayAction)

    @property
    @_requires_action
    def cancel(self):
        """
        `True` if the action was cancelling other actions.
        """
        return isinstance(self.action, _tl.SendMessageCancelAction)

    @property
    @_requires_action
    def geo(self):
        """
        `True` if what's being uploaded is a geo.
        """
        return isinstance(self.action, _tl.SendMessageGeoLocationAction)

    @property
    @_requires_action
    def audio(self):
        """
        `True` if what's being recorded/uploaded is an audio.
        """
        return isinstance(self.action, (
            _tl.SendMessageRecordAudioAction,
            _tl.SendMessageUploadAudioAction
        ))

    @property
    @_requires_action
    def round(self):
        """
        `True` if what's being recorded/uploaded is a round video.
        """
        return isinstance(self.action, (
            _tl.SendMessageRecordRoundAction,
            _tl.SendMessageUploadRoundAction
        ))

    @property
    @_requires_action
    def video(self):
        """
        `True` if what's being recorded/uploaded is an video.
        """
        return isinstance(self.action, (
            _tl.SendMessageRecordVideoAction,
            _tl.SendMessageUploadVideoAction
        ))

    @property
    @_requires_action
    def contact(self):
        """
        `True` if what's being uploaded (selected) is a contact.
        """
        return isinstance(self.action, _tl.SendMessageChooseContactAction)

    @property
    @_requires_action
    def document(self):
        """
        `True` if what's being uploaded is document.
        """
        return isinstance(self.action, _tl.SendMessageUploadDocumentAction)

    @property
    @_requires_action
    def sticker(self):
        """
        `True` if what's being uploaded is a sticker.
        """
        return isinstance(self.action, _tl.SendMessageChooseStickerAction)

    @property
    @_requires_action
    def photo(self):
        """
        `True` if what's being uploaded is a photo.
        """
        return isinstance(self.action, _tl.SendMessageUploadPhotoAction)

    @property
    @_requires_action
    def last_seen(self):
        """
        Exact `datetime.datetime` when the user was last seen if known.
        """
        if isinstance(self.status, _tl.UserStatusOffline):
            return self.status.was_online

    @property
    @_requires_status
    def until(self):
        """
        The `datetime.datetime` until when the user should appear online.
        """
        if isinstance(self.status, _tl.UserStatusOnline):
            return self.status.expires

    def _last_seen_delta(self):
        if isinstance(self.status, _tl.UserStatusOffline):
            return datetime.datetime.now(tz=datetime.timezone.utc) - self.status.was_online
        elif isinstance(self.status, _tl.UserStatusOnline):
            return datetime.timedelta(days=0)
        elif isinstance(self.status, _tl.UserStatusRecently):
            return datetime.timedelta(days=1)
        elif isinstance(self.status, _tl.UserStatusLastWeek):
            return datetime.timedelta(days=7)
        elif isinstance(self.status, _tl.UserStatusLastMonth):
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
