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
    async def entity(self):
        return await self._client.get_entity(self._peer)

    @property
    async def input_entity(self):
        return await self._client.get_input_entity(self._peer)

    @property
    def text(self):
        return self._text

    @property
    def raw_text(self):
        return self._raw_text

    async def set_message(self, text=None, reply_to=0, parse_mode='md',
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

        raw_text, entities = await self._client._parse_message_text(text,
                                                                    parse_mode)
        result = await self._client(SaveDraftRequest(
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

        return result

    async def send(self, clear=True, parse_mode='md'):
        await self._client.send_message(self._peer, self.text,
                                        reply_to=self.reply_to_msg_id,
                                        link_preview=self.link_preview,
                                        parse_mode=parse_mode,
                                        clear_draft=clear)

    async def delete(self):
        """
        Deletes this draft
        :return bool: ``True`` on success
        """
        return await self.set_message(text='')
