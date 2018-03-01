from ..functions.messages import SaveDraftRequest
from ..types import UpdateDraftMessage, DraftMessage


class Draft:
    """
    Custom class that encapsulates a draft on the Telegram servers, providing
    an abstraction to change the message conveniently. The library will return
    instances of this class when calling ``client.get_drafts()``.
    """
    def __init__(self, client, peer, draft):
        self._client = client
        self._peer = peer
        if not draft:
            draft = DraftMessage('', None, None, None, None)

        self.text = draft.message
        self.date = draft.date
        self.no_webpage = draft.no_webpage
        self.reply_to_msg_id = draft.reply_to_msg_id
        self.entities = draft.entities

    @classmethod
    def _from_update(cls, client, update):
        if not isinstance(update, UpdateDraftMessage):
            raise TypeError(
                'You can only create a new `Draft` from a corresponding '
                '`UpdateDraftMessage` object.'
            )

        return cls(client=client, peer=update.peer, draft=update.draft)

    @property
    def entity(self):
        return self._client.get_entity(self._peer)

    @property
    def input_entity(self):
        return self._client.get_input_entity(self._peer)

    def set_message(self, text, no_webpage=None, reply_to_msg_id=None, entities=None):
        """
        Changes the draft message on the Telegram servers. The changes are
        reflected in this object. Changing only individual attributes like for
        example the ``reply_to_msg_id`` should be done by providing the current
        values of this object, like so:

            draft.set_message(
                draft.text,
                no_webpage=draft.no_webpage,
                reply_to_msg_id=NEW_VALUE,
                entities=draft.entities
            )

        :param str text: New text of the draft
        :param bool no_webpage: Whether to attach a web page preview
        :param int reply_to_msg_id: Message id to reply to
        :param list entities: A list of formatting entities
        :return bool: ``True`` on success
        """
        result = self._client(SaveDraftRequest(
            peer=self._peer,
            message=text,
            no_webpage=no_webpage,
            reply_to_msg_id=reply_to_msg_id,
            entities=entities
        ))

        if result:
            self.text = text
            self.no_webpage = no_webpage
            self.reply_to_msg_id = reply_to_msg_id
            self.entities = entities

        return result

    def delete(self):
        """
        Deletes this draft
        :return bool: ``True`` on success
        """
        return self.set_message(text='')
