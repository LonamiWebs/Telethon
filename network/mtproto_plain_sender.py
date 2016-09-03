# This file is based on TLSharp
# https://github.com/sochix/TLSharp/blob/master/TLSharp.Core/Network/MtProtoPlainSender.cs
import time
from utils.binary_writer import BinaryWriter
from utils.binary_reader import BinaryReader


class MtProtoPlainSender:
    """MTProto Mobile Protocol plain sender (https://core.telegram.org/mtproto/description#unencrypted-messages)"""
    def __init__(self, transport):
        self._sequence = 0
        self._time_offset = 0
        self._last_msg_id = 0
        self._transport = transport

    def send(self, data):
        """Sends a plain packet (auth_key_id = 0) containing the given message body (data)"""
        with BinaryWriter() as writer:
            writer.write_long(0)
            writer.write_long(self.get_new_msg_id())
            writer.write_int(len(data))
            writer.write(data)

            packet = writer.get_bytes()
            self._transport.send(packet)

    def receive(self):
        """Receives a plain packet, returning the body of the response"""
        result = self._transport.receive()
        with BinaryReader(result.body) as reader:
            auth_key_id = reader.read_long()
            msg_id = reader.read_long()
            message_length = reader.read_int()

            response = reader.read(message_length)
            return response

    def get_new_msg_id(self):
        """Generates a new message ID based on the current time (in ms) since epoch"""
        new_msg_id = int(self._time_offset + time.time() * 1000)  # Multiply by 1000 to get milliseconds

        # Ensure that we always return a message ID which is higher than the previous one
        if self._last_msg_id >= new_msg_id:
            new_msg_id = self._last_msg_id + 4

        self._last_msg_id = new_msg_id
        return new_msg_id
