from __future__ import annotations

import abc
import base64
import re
import struct
from typing import Optional, Self, TypeAlias

from ...tl import abcs, types

PeerIdentifier: TypeAlias = int
PeerAuth: TypeAlias = Optional[int]

USER_PREFIX = "u."
GROUP_PREFIX = "g."
CHANNEL_PREFIX = "c."


class PeerRef(abc.ABC):
    """
    A reference to a :term:`peer`.

    References can be used to interact with any method that expects a peer,
    without the need to fetch or resolve the entire peer beforehand.

    A reference consists of both an identifier and the authorization to access the peer.
    The proof of authorization is represented by Telegram's access hash witness.

    You can access the :attr:`telethon.types.Peer.ref` attribute on :class:`~telethon.types.User`,
    :class:`~telethon.types.Group` or :class:`~telethon.types.Channel` to obtain it.

    Not all references are always valid in all contexts.
    Under certain conditions, it is possible for a reference without an authorization to be usable,
    and for a reference with an authorization to not be usable everywhere.
    The exact rules are defined by Telegram and could change any time.

    .. seealso::

        :doc:`/concepts/peers`
    """

    __slots__ = ("identifier", "authorization")

    def __init__(
        self, identifier: PeerIdentifier, authorization: PeerAuth = None
    ) -> None:
        assert (
            identifier >= 0
        ), "PeerRef identifiers must be positive; see the documentation for Peers"
        self.identifier = identifier
        self.authorization = authorization

    @classmethod
    def from_str(cls, string: str, /) -> UserRef | GroupRef | ChannelRef:
        """
        Create a reference back from its string representation:

        :param string:
            The :class:`str` representation of the :class:`PeerRef`.

        .. rubric:: Example

        .. code-block:: python

            ref: PeerRef = ...
            assert PeerRef.from_str(str(ref)) == ref
        """
        if match := re.match(r"(\w\.)(\d+)\.([^.]+)", string):
            prefix, iden, auth = match.groups()

            identifier = int(iden)

            if auth == "0":
                authorization: Optional[int] = None
            else:
                try:
                    (authorization,) = struct.unpack(
                        "!q", base64.urlsafe_b64decode(auth.encode("ascii") + b"=")
                    )
                except Exception:
                    raise ValueError(f"invalid PeerRef string: {string!r}")

            if prefix == USER_PREFIX:
                return UserRef(identifier, authorization)
            elif prefix == GROUP_PREFIX:
                return GroupRef(identifier, authorization)
            elif prefix == CHANNEL_PREFIX:
                return ChannelRef(identifier, authorization)

        raise ValueError(f"invalid PeerRef string: {string!r}")

    @classmethod
    def _empty_from_peer(cls, peer: abcs.Peer) -> UserRef | GroupRef | ChannelRef:
        if isinstance(peer, types.PeerUser):
            return UserRef(peer.user_id, None)
        elif isinstance(peer, types.PeerChat):
            return GroupRef(peer.chat_id, None)
        elif isinstance(peer, types.PeerChannel):
            return ChannelRef(peer.channel_id, None)
        else:
            raise RuntimeError("unexpected case")

    @abc.abstractmethod
    def _to_peer(self) -> abcs.Peer:
        pass

    @abc.abstractmethod
    def _to_input_peer(self) -> abcs.InputPeer:
        pass

    @abc.abstractmethod
    def __str__(self) -> str:
        """
        Format the reference into a :class:`str`.

        .. seealso::

            :doc:`/concepts/messages`, to learn how this can be used to format inline mentions in messages.
        """

    def __repr__(self) -> str:
        """
        Format the reference in a way that's easy to debug.
        """
        return f"{self.__class__.__name__}({self.identifier}, {self.authorization})"

    def _encode_str(self) -> str:
        if self.authorization is None:
            auth = "0"
        else:
            auth = (
                base64.urlsafe_b64encode(struct.pack("!q", self.authorization))
                .decode("ascii")
                .rstrip("=")
            )

        return f"{self.identifier}.{auth}"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, self.__class__):
            return NotImplemented
        return (
            self.identifier == other.identifier
            and self.authorization == other.authorization
        )

    @property
    def _ref(self) -> UserRef | GroupRef | ChannelRef:
        assert isinstance(self, (UserRef, GroupRef, ChannelRef))
        return self


class UserRef(PeerRef):
    """
    A user reference.

    This includes both user accounts and bot accounts, and corresponds to a bare Telegram :tl:`user`.
    """

    @classmethod
    def from_str(cls, string: str, /) -> Self:
        ref = super().from_str(string)
        if not isinstance(ref, cls):
            raise TypeError("PeerRef string does not belong to UserRef")

        return ref

    def _to_peer(self) -> abcs.Peer:
        return types.PeerUser(user_id=self.identifier)

    def _to_input_peer(self) -> abcs.InputPeer:
        return types.InputPeerUser(
            user_id=self.identifier, access_hash=self.authorization or 0
        )

    def _to_input_user(self) -> types.InputUser:
        return types.InputUser(
            user_id=self.identifier, access_hash=self.authorization or 0
        )

    def __str__(self) -> str:
        return f"{USER_PREFIX}{self._encode_str()}"

    @property
    def _ref(self) -> Self:
        return self


class GroupRef(PeerRef):
    """
    A group reference.

    This only includes small group chats, and corresponds to a bare Telegram :tl:`chat`.
    """

    @classmethod
    def from_str(cls, string: str, /) -> Self:
        ref = super().from_str(string)
        if not isinstance(ref, cls):
            raise TypeError("PeerRef string does not belong to GroupRef")

        return ref

    def _to_peer(self) -> abcs.Peer:
        return types.PeerChat(chat_id=self.identifier)

    def _to_input_peer(self) -> abcs.InputPeer:
        return types.InputPeerChat(chat_id=self.identifier)

    def _to_input_chat(self) -> int:
        return self.identifier

    def __str__(self) -> str:
        return f"{GROUP_PREFIX}{self._encode_str()}"

    @property
    def _ref(self) -> Self:
        return self


class ChannelRef(PeerRef):
    """
    A channel reference.

    This includes broadcast channels, megagroups and gigagroups, and corresponds to a bare Telegram :tl:`channel`.
    """

    @classmethod
    def from_str(cls, string: str, /) -> Self:
        ref = super().from_str(string)
        if not isinstance(ref, cls):
            raise TypeError("PeerRef string does not belong to ChannelRef")

        return ref

    def _to_peer(self) -> abcs.Peer:
        return types.PeerChannel(channel_id=self.identifier)

    def _to_input_peer(self) -> abcs.InputPeer:
        return types.InputPeerChannel(
            channel_id=self.identifier, access_hash=self.authorization or 0
        )

    def _to_input_channel(self) -> types.InputChannel:
        return types.InputChannel(
            channel_id=self.identifier, access_hash=self.authorization or 0
        )

    def __str__(self) -> str:
        return f"{CHANNEL_PREFIX}{self._encode_str()}"

    @property
    def _ref(self) -> Self:
        return self
