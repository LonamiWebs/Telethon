import logging
import re
from abc import ABC, abstractmethod
from typing import List, NewType, Optional, Self, Tuple

from ...tl.mtproto.types import RpcError as GeneratedRpcError

MsgId = NewType("MsgId", int)


class Update:
    """
    An update that does not belong to any RPC.
    """

    __slots__ = ("body",)

    def __init__(self, body: bytes):
        self.body = body


class RpcResult:
    """
    A response that belongs to the RPC associated with this message identifier.
    """

    __slots__ = ("msg_id", "body")

    def __init__(self, msg_id: MsgId, body: bytes):
        self.msg_id = msg_id
        self.body = body


class RpcError(ValueError):
    """
    A Remote Procedure Call Error.

    Only occurs when the answer to a request sent to Telegram is not the expected result.
    The library will never construct instances of this error by itself.

    This is the parent class of all :data:`telethon.errors` subtypes.

    :param code: See below.
    :param name: See below.
    :param value: See below.
    :param caused_by: Constructor identifier of the request that caused the error.

    .. seealso::

        :doc:`/concepts/errors`
    """

    def __init__(
        self,
        *args: object,
        msg_id: MsgId = MsgId(0),
        code: int = 0,
        name: str = "",
        value: Optional[int] = None,
        caused_by: Optional[int] = None,
    ) -> None:
        append_value = f" ({value})" if value else ""
        super().__init__(f"rpc error {code}: {name}{append_value}", *args)

        self.msg_id = msg_id
        self._code = code
        self._name = name
        self._value = value
        self._caused_by = caused_by

    @property
    def code(self) -> int:
        """
        Integer code of the error.

        This usually reassembles an `HTTP status code <https://developer.mozilla.org/en-US/docs/Web/HTTP/Status>`_.
        """
        return self._code

    @property
    def name(self) -> str:
        """
        Name of the error, usually in ``SCREAMING_CASE``.
        """
        return self._name

    @property
    def value(self) -> Optional[int]:
        """
        Integer value contained within the error.

        For example, if the :attr:`name` is ``'FLOOD_WAIT'``, this would be the number of seconds.
        """
        return self._value

    @classmethod
    def _from_mtproto_error(cls, error: GeneratedRpcError) -> Self:
        if m := re.search(r"-?\d+", error.error_message):
            name = re.sub(
                r"_{2,}",
                "_",
                error.error_message[: m.start()] + error.error_message[m.end() :],
            ).strip("_")
            value = int(m[0])
        else:
            name = error.error_message
            value = None

        return cls(
            code=error.error_code,
            name=name,
            value=value,
            caused_by=None,
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, self.__class__):
            return NotImplemented
        return (
            self._code == other._code
            and self._name == other._name
            and self._value == other._value
        )


# https://core.telegram.org/mtproto/service_messages_about_messages
BAD_MSG_DESCRIPTIONS = {
    16: "msg_id too low",
    17: "msg_id too high",
    18: "incorrect two lower order msg_id bits",
    19: "container msg_id is the same as msg_id of a previously received message",
    20: "message too old, and it cannot be verified whether the server has received a message with this msg_id or not",
    32: "msg_seqno too low",
    33: "msg_seqno too high",
    34: "an even msg_seqno expected, but odd received",
    35: "odd msg_seqno expected, but even received",
    48: "incorrect server salt",
    64: "invalid container",
}

RETRYABLE_MSG_IDS = {16, 17, 48}
NON_FATAL_MSG_IDS = RETRYABLE_MSG_IDS & {32, 33}


class BadMessage(ValueError):
    def __init__(
        self,
        *args: object,
        msg_id: MsgId = MsgId(0),
        code: int,
        caused_by: Optional[int] = None,
    ) -> None:
        description = BAD_MSG_DESCRIPTIONS.get(code) or "no description available"
        super().__init__(f"bad msg={code}: {description}", *args)

        self.msg_id = msg_id
        self._code = code
        self._caused_by = caused_by
        self.severity = (
            logging.WARNING if self._code in NON_FATAL_MSG_IDS else logging.ERROR
        )

    @property
    def code(self) -> int:
        return self._code

    @property
    def retryable(self) -> bool:
        return self._code in RETRYABLE_MSG_IDS

    @property
    def fatal(self) -> bool:
        return self._code not in NON_FATAL_MSG_IDS

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, self.__class__):
            return NotImplemented
        return self._code == other._code


Deserialization = Update | RpcResult | RpcError | BadMessage


# https://core.telegram.org/mtproto/description
class Mtp(ABC):
    @abstractmethod
    def push(self, request: bytes) -> Optional[MsgId]:
        """
        Push a request's body to the internal buffer.

        On success, return the serialized message identifier.
        """

    @abstractmethod
    def finalize(self) -> Optional[Tuple[MsgId, bytes]]:
        """
        Finalize the buffer of serialized requests.

        If the buffer is empty, :data:`None` is returned.
        Otherwise, the message identifier for the entire buffer and the serialized buffer are returned.
        """

    @abstractmethod
    def deserialize(self, payload: bytes) -> List[Deserialization]:
        """
        Deserialize incoming buffer payload.
        """
