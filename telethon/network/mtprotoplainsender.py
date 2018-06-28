"""
This module contains the class used to communicate with Telegram's servers
in plain text, when no authorization key has been created yet.
"""
import struct

from .mtprotostate import MTProtoState
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
        self._state = MTProtoState(auth_key=None)
        self._connection = connection

    async def send(self, request):
        """
        Sends and receives the result for the given request.
        """
        body = bytes(request)
        msg_id = self._state._get_new_msg_id()
        await self._connection.send(
            struct.pack('<QQi', 0, msg_id, len(body)) + body
        )

        body = await self._connection.recv()
        if body == b'l\xfe\xff\xff':  # -404 little endian signed
            # Broken authorization, must reset the auth key
            raise BrokenAuthKeyError()

        with BinaryReader(body) as reader:
            assert reader.read_long() == 0, 'Bad auth_key_id'  # auth_key_id

            assert reader.read_long() != 0,  'Bad msg_id'  # msg_id
            # ^ We should make sure that the read ``msg_id`` is greater
            # than our own ``msg_id``. However, under some circumstances
            # (bad system clock/working behind proxies) this seems to not
            # be the case, which would cause endless assertion errors.

            assert reader.read_int() > 0,  'Bad length'  # length
            # We could read length bytes and use those in a new reader to read
            # the next TLObject without including the padding, but since the
            # reader isn't used for anything else after this, it's unnecessary.
            return reader.tgread_object()
