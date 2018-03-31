"""
This module contains the class used to communicate with Telegram's servers
in plain text, when no authorization key has been created yet.
"""
import struct
import time

from ..errors import BrokenAuthKeyError
from ..extensions import BinaryReader


class MtProtoPlainSender:
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

    def connect(self):
        """Connects to Telegram's servers."""
        self._connection.connect()

    def disconnect(self):
        """Disconnects from Telegram's servers."""
        self._connection.close()

    def send(self, data):
        """
        Sends a plain packet (auth_key_id = 0) containing the
        given message body (data).

        :param data: the data to be sent.
        """
        self._connection.send(
            struct.pack('<QQi', 0, self._get_new_msg_id(), len(data)) + data
        )

    def receive(self):
        """
        Receives a plain packet from the network.

        :return: the response body.
        """
        body = self._connection.recv()
        if body == b'l\xfe\xff\xff':  # -404 little endian signed
            # Broken authorization, must reset the auth key
            raise BrokenAuthKeyError()

        with BinaryReader(body) as reader:
            reader.read_long()  # auth_key_id
            reader.read_long()  # msg_id
            message_length = reader.read_int()

            response = reader.read(message_length)
            return response

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
