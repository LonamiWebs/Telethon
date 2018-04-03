from . import Draft
from .. import TLObject
from ... import utils


class Dialog:
    """
    Custom class that encapsulates a dialog (an open "conversation" with
    someone, a group or a channel) providing an abstraction to easily
    access the input version/normal entity/message etc. The library will
    return instances of this class when calling :meth:`.get_dialogs()`.

    Args:
        dialog (:tl:`Dialog`):
            The original ``Dialog`` instance.

        pinned (`bool`):
            Whether this dialog is pinned to the top or not.

        message (:tl:`Message`):
            The last message sent on this dialog. Note that this member
            will not be updated when new messages arrive, it's only set
            on creation of the instance.

        date (`datetime`):
            The date of the last message sent on this dialog.

        entity (`entity`):
            The entity that belongs to this dialog (user, chat or channel).

        input_entity (:tl:`InputPeer`):
            Input version of the entity.

        id (`int`):
            The marked ID of the entity, which is guaranteed to be unique.

        name (`str`):
            Display name for this dialog. For chats and channels this is
            their title, and for users it's "First-Name Last-Name".

        unread_count (`int`):
            How many messages are currently unread in this dialog. Note that
            this value won't update when new messages arrive.

        unread_mentions_count (`int`):
            How many mentions are currently unread in this dialog. Note that
            this value won't update when new messages arrive.

        draft (`telethon.tl.custom.draft.Draft`):
            The draft object in this dialog. It will not be ``None``,
            so you can call ``draft.set_message(...)``.
    """
    def __init__(self, client, dialog, entities, messages):
        # Both entities and messages being dicts {ID: item}
        self._client = client
        self.dialog = dialog
        self.pinned = bool(dialog.pinned)
        self.message = messages.get(dialog.top_message, None)
        self.date = getattr(self.message, 'date', None)

        self.entity = entities[utils.get_peer_id(dialog.peer)]
        self.input_entity = utils.get_input_peer(self.entity)
        self.id = utils.get_peer_id(self.entity)  # ^ May be InputPeerSelf()
        self.name = utils.get_display_name(self.entity)

        self.unread_count = dialog.unread_count
        self.unread_mentions_count = dialog.unread_mentions_count

        self.draft = Draft(client, dialog.peer, dialog.draft)

    def send_message(self, *args, **kwargs):
        """
        Sends a message to this dialog. This is just a wrapper around
        ``client.send_message(dialog.input_entity, *args, **kwargs)``.
        """
        return self._client.send_message(self.input_entity, *args, **kwargs)

    def to_dict(self):
        return {
            '_': 'Dialog',
            'name': self.name,
            'date': self.date,
            'draft': self.draft,
            'message': self.message,
            'entity': self.entity,
        }

    def __str__(self):
        return TLObject.pretty_format(self.to_dict())

    def stringify(self):
        return TLObject.pretty_format(self.to_dict(), indent=0)
