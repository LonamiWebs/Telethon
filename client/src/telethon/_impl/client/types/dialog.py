from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Self

from ...tl import abcs, types
from .draft import Draft
from .message import Message
from .meta import NoPublicConstructor
from .peer import Peer, peer_id

if TYPE_CHECKING:
    from ..client.client import Client


class Dialog(metaclass=NoPublicConstructor):
    """
    A dialog.

    This represents an open conversation your chat list.

    This includes the groups you've joined, channels you've subscribed to, and open one-to-one private conversations.

    You can obtain dialogs with methods such as :meth:`telethon.Client.get_dialogs`.
    """

    def __init__(
        self,
        client: Client,
        raw: types.Dialog | types.DialogFolder,
        chat_map: dict[int, Peer],
        msg_map: dict[int, Message],
    ) -> None:
        self._client = client
        self._raw = raw
        self._chat_map = chat_map
        self._msg_map = msg_map

    @classmethod
    def _from_raw(
        cls,
        client: Client,
        dialog: abcs.Dialog,
        chat_map: dict[int, Peer],
        msg_map: dict[int, Message],
    ) -> Self:
        assert isinstance(dialog, (types.Dialog, types.DialogFolder))
        return cls._create(client, dialog, chat_map, msg_map)

    @property
    def chat(self) -> Peer:
        """
        The chat where messages are sent in this dialog.
        """
        return self._chat_map[peer_id(self._raw.peer)]

    @property
    def draft(self) -> Optional[Draft]:
        """
        The message draft within this dialog, if any.

        This property does not update when the draft changes.
        """
        if isinstance(self._raw, types.Dialog) and self._raw.draft:
            return Draft._from_raw(
                self._client,
                self._raw.peer,
                self._raw.top_message,
                self._raw.draft,
                self._chat_map,
            )
        else:
            return None

    @property
    def latest_message(self) -> Optional[Message]:
        """
        The latest message sent or received in this dialog, if any.

        This property does not update when new messages arrive.
        """
        return self._msg_map.get(self._raw.top_message)

    @property
    def unread_count(self) -> int:
        """
        The amount of unread messages in this dialog.

        This property does not update when messages are read or sent.
        """
        if isinstance(self._raw, types.Dialog):
            return self._raw.unread_count
        elif isinstance(self._raw, types.DialogPeerFolder):
            return self._raw.unread_unmuted_messages_count + self._raw.unread_muted_messages_count
        else:
            raise RuntimeError("unexpected case")
