from . import Draft
from ... import utils


class Dialog:
    """
    Custom class that encapsulates a dialog (an open "conversation" with
    someone, a group or a channel) providing an abstraction to easily
    access the input version/normal entity/message etc. The library will
    return instances of this class when calling `client.get_dialogs()`.
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
        self.name = utils.get_display_name(self.entity)

        self.unread_count = dialog.unread_count
        self.unread_mentions_count = dialog.unread_mentions_count

        self.draft = Draft(client, dialog.peer, dialog.draft)

    def send_message(self, *args, **kwargs):
        """
        Sends a message to this dialog. This is just a wrapper around
        client.send_message(dialog.input_entity, *args, **kwargs).
        """
        return self._client.send_message(self.input_entity, *args, **kwargs)
