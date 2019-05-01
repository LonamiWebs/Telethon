from .chatgetter import ChatGetter
from .sendergetter import SenderGetter
from ... import utils
from ...tl import types


class Forward(ChatGetter, SenderGetter):
    """
    Custom class that encapsulates a :tl:`MessageFwdHeader` providing an
    abstraction to easily access information like the original sender.

    Remember that this class implements `ChatGetter
    <telethon.tl.custom.chatgetter.ChatGetter>` and `SenderGetter
    <telethon.tl.custom.sendergetter.SenderGetter>` which means you
    have access to all their sender and chat properties and methods.

    Attributes:

        original_fwd (:tl:`MessageFwdHeader`):
            The original :tl:`MessageFwdHeader` instance.

        Any other attribute:
            Attributes not described here are the same as those available
            in the original :tl:`MessageFwdHeader`.
    """
    def __init__(self, client, original, entities):
        self.__dict__ = original.__dict__
        self._client = client
        self.original_fwd = original

        self._sender_id = original.from_id
        self._sender, self._input_sender = utils._get_entity_pair(
            original.from_id, entities, client._entity_cache)

        self._broadcast = None
        if original.channel_id:
            self._chat_peer = types.PeerChannel(original.channel_id)

            self._chat, self._input_chat = utils._get_entity_pair(
                 self.chat_id, entities, client._entity_cache)
        else:
            self._chat = self._input_chat = self._chat_peer = None

    # TODO We could reload the message
