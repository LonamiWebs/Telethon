from ..functions.messages import SaveDraftRequest
from ..types import UpdateDraftMessage, DraftMessage
from ...extensions import markdown


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

        self._text = markdown.unparse(draft.message, draft.entities)
        self._raw_text = draft.message
        self.date = draft.date
        self.no_webpage = draft.no_webpage
        self.reply_to_msg_id = draft.reply_to_msg_id

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

    @property
    def text(self):
        return self._text

    @property
    def raw_text(self):
        return self._raw_text

    def set_message(self, text, no_webpage=None, reply_to_msg_id=None,
                    parse_mode='md'):
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

        :param str text: New text of the draft.
        :param bool no_webpage: Whether to attach a web page preview.
        :param int reply_to_msg_id: Message id to reply to.
        :param str parse_mode: The parse mode to be used for the text.
        :return bool: ``True`` on success.
        """
        raw_text, entities = self._client._parse_message_text(text, parse_mode)
        result = self._client(SaveDraftRequest(
            peer=self._peer,
            message=raw_text,
            no_webpage=no_webpage,
            reply_to_msg_id=reply_to_msg_id,
            entities=entities
        ))

        if result:
            self._text = text
            self._raw_text = raw_text
            self.no_webpage = no_webpage
            self.reply_to_msg_id = reply_to_msg_id

        return result

    def send(self, clear=True, parse_mode='md'):
        self._client.send_message(self._peer, self.text,
                                  reply_to=self.reply_to_msg_id,
                                  link_preview=not self.no_webpage,
                                  parse_mode=parse_mode,
                                  clear_draft=clear)

    def delete(self):
        """
        Deletes this draft
        :return bool: ``True`` on success
        """
        return self.set_message(text='')
