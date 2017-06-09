import random
import time

from ..extensions import BinaryReader, BinaryWriter


class MtProtoPlainSender:
    """MTProto Mobile Protocol plain sender (https://core.telegram.org/mtproto/description#unencrypted-messages)"""

    def __init__(self, transport):
        self._sequence = 0
        self._time_offset = 0
        self._last_msg_id = 0
        self._transport = transport

    def connect(self):
        self._transport.connect()

    def disconnect(self):
        self._transport.close()

    def send(self, data):
        """Sends a plain packet (auth_key_id = 0) containing the given message body (data)"""
        with BinaryWriter() as writer:
            writer.write_long(0)
            writer.write_long(self._get_new_msg_id())
            writer.write_int(len(data))
            writer.write(data)

            packet = writer.get_bytes()
            self._transport.send(packet)

    def receive(self):
        """Receives a plain packet, returning the body of the response"""
        seq, body = self._transport.receive()
        with BinaryReader(body) as reader:
            reader.read_long()  # auth_key_id
            reader.read_long()  # msg_id
            message_length = reader.read_int()

            response = reader.read(message_length)
            return response

    def _get_new_msg_id(self):
        """Generates a new message ID based on the current time (in ms) since epoch"""
        # See https://core.telegram.org/mtproto/description#message-identifier-msg-id
        ms_time = int(time.time() * 1000)
        new_msg_id = (((ms_time // 1000) << 32)
                      |  # "must approximately equal unix time*2^32"
                      ((ms_time % 1000) << 22)
                      |  # "approximate moment in time the message was created"
                      random.randint(0, 524288)
                      << 2)  # "message identifiers are divisible by 4"

        # Ensure that we always return a message ID which is higher than the previous one
        if self._last_msg_id >= new_msg_id:
            new_msg_id = self._last_msg_id + 4

        self._last_msg_id = new_msg_id
        return new_msg_id
