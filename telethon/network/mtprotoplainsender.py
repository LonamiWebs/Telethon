"""
This module contains the class used to communicate with Telegram's servers
in plain text, when no authorization key has been created yet.
"""
import struct
import time

from ..errors import BrokenAuthKeyError
from ..extensions import BinaryReader


class MTProtoPlainSender:
    """
    MTProto Mobile Protocol plain sender
    (https://core.telegram.org/mtproto/description#unencrypted-messages)
    """
    def __init__(self, connection):
        """
        Initializes the MTProto plain sender.

        :param connection: the Connection to be used.
        """
        self._sequence = 0
        self._time_offset = 0
        self._last_msg_id = 0
        self._connection = connection

    async def send(self, request):
        """
        Sends and receives the result for the given request.
        """
        body = bytes(request)
        msg_id = self._get_new_msg_id()
        await self._connection.send(
            struct.pack('<QQi', 0, msg_id, len(body)) + body
        )

        body = await self._connection.recv()
        if body == b'l\xfe\xff\xff':  # -404 little endian signed
            # Broken authorization, must reset the auth key
            raise BrokenAuthKeyError()

        with BinaryReader(body) as reader:
            assert reader.read_long() == 0  # auth_key_id
            assert reader.read_long() > msg_id  # msg_id
            assert reader.read_int()  # length
            # No need to read "length" bytes first, just read the object
            return reader.tgread_object()

    def _get_new_msg_id(self):
        """Generates a new message ID based on the current time since epoch."""
        # See core.telegram.org/mtproto/description#message-identifier-msg-id
        now = time.time()
        nanoseconds = int((now - int(now)) * 1e+9)
        # "message identifiers are divisible by 4"
        new_msg_id = (int(now) << 32) | (nanoseconds << 2)
        if self._last_msg_id >= new_msg_id:
            new_msg_id = self._last_msg_id + 4

        self._last_msg_id = new_msg_id
        return new_msg_id
