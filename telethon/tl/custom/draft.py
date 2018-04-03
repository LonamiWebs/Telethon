import datetime

from .. import TLObject
from ..functions.messages import SaveDraftRequest
from ..types import UpdateDraftMessage, DraftMessage
from ...errors import RPCError
from ...extensions import markdown


class Draft:
    """
    Custom class that encapsulates a draft on the Telegram servers, providing
    an abstraction to change the message conveniently. The library will return
    instances of this class when calling :meth:`get_drafts()`.

    Args:
        date (`datetime`):
            The date of the draft.

        link_preview (`bool`):
            Whether the link preview is enabled or not.

        reply_to_msg_id (`int`):
            The message ID that the draft will reply to.
    """
    def __init__(self, client, peer, draft):
        self._client = client
        self._peer = peer
        if not draft:
            draft = DraftMessage('', None, None, None, None)

        self._text = markdown.unparse(draft.message, draft.entities)
        self._raw_text = draft.message
        self.date = draft.date
        self.link_preview = not draft.no_webpage
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
        """
        The entity that belongs to this dialog (user, chat or channel).
        """
        return self._client.get_entity(self._peer)

    @property
    def input_entity(self):
        """
        Input version of the entity.
        """
        return self._client.get_input_entity(self._peer)

    @property
    def text(self):
        """
        The markdown text contained in the draft. It will be
        empty if there is no text (and hence no draft is set).
        """
        return self._text

    @property
    def raw_text(self):
        """
        The raw (text without formatting) contained in the draft.
        It will be empty if there is no text (thus draft not set).
        """
        return self._raw_text

    @property
    def is_empty(self):
        """
        Convenience bool to determine if the draft is empty or not.
        """
        return not self._text

    def set_message(self, text=None, reply_to=0, parse_mode='md',
                    link_preview=None):
        """
        Changes the draft message on the Telegram servers. The changes are
        reflected in this object.

        :param str text: New text of the draft.
                         Preserved if left as None.

        :param int reply_to: Message ID to reply to.
                             Preserved if left as 0, erased if set to None.

        :param bool link_preview: Whether to attach a web page preview.
                                  Preserved if left as None.

        :param str parse_mode: The parse mode to be used for the text.
        :return bool: ``True`` on success.
        """
        if text is None:
            text = self._text

        if reply_to == 0:
            reply_to = self.reply_to_msg_id

        if link_preview is None:
            link_preview = self.link_preview

        raw_text, entities = self._client._parse_message_text(text, parse_mode)
        result = self._client(SaveDraftRequest(
            peer=self._peer,
            message=raw_text,
            no_webpage=not link_preview,
            reply_to_msg_id=reply_to,
            entities=entities
        ))

        if result:
            self._text = text
            self._raw_text = raw_text
            self.link_preview = link_preview
            self.reply_to_msg_id = reply_to
            self.date = datetime.datetime.now()

        return result

    def send(self, clear=True, parse_mode='md'):
        """
        Sends the contents of this draft to the dialog. This is just a
        wrapper around ``send_message(dialog.input_entity, *args, **kwargs)``.
        """
        self._client.send_message(self._peer, self.text,
                                  reply_to=self.reply_to_msg_id,
                                  link_preview=self.link_preview,
                                  parse_mode=parse_mode,
                                  clear_draft=clear)

    def delete(self):
        """
        Deletes this draft, and returns ``True`` on success.
        """
        return self.set_message(text='')

    def to_dict(self):
        try:
            entity = self.entity
        except RPCError as e:
            entity = e

        return {
            '_': 'Draft',
            'text': self.text,
            'entity': entity,
            'date': self.date,
            'link_preview': self.link_preview,
            'reply_to_msg_id': self.reply_to_msg_id
        }

    def __str__(self):
        return TLObject.pretty_format(self.to_dict())

    def stringify(self):
        return TLObject.pretty_format(self.to_dict(), indent=0)
