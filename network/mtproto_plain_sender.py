
import time
from utils.binary_writer import BinaryWriter
from utils.binary_reader import BinaryReader


class MtProtoPlainSender:

    def __init__(self, transport):
        self._sequence = 0
        self._time_offset = 0
        self._last_msg_id = 0
        self._transport = transport

    def send(self, data):
        with BinaryWriter() as writer:
            writer.write_long(0)
            writer.write_int(self.get_new_msg_id())
            writer.write_int(len(data))
            writer.write(data)

            packet = writer.get_bytes()
            self._transport.send(packet)

    def receive(self):
        result = self._transport.receive()
        with BinaryReader(result.body) as reader:
            auth_key_id = reader.read_long()
            message_id = reader.read_long()
            message_length = reader.read_int()

            response = reader.read(message_length)
            return response

    def get_new_msg_id(self):
        new_msg_id = int(self._time_offset + time.time() * 1000)  # multiply by 1000 to get milliseconds

        if self._last_msg_id >= new_msg_id:
            new_msg_id = self._last_msg_id + 4

        self._last_msg_id = new_msg_id
        return new_msg_id
