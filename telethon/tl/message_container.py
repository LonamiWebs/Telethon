from . import TLObject, GzipPacked
from ..extensions import BinaryWriter


class MessageContainer(TLObject):
    constructor_id = 0x73f1f8dc

    def __init__(self, messages):
        super().__init__()
        self.content_related = False
        self.messages = messages

    def to_bytes(self):
        # TODO Change this to delete the on_send from this class
        with BinaryWriter() as writer:
            writer.write_int(MessageContainer.constructor_id, signed=False)
            writer.write_int(len(self.messages))
            for m in self.messages:
                writer.write(m.to_bytes())

            return writer.get_bytes()

    @staticmethod
    def iter_read(reader):
        reader.read_int(signed=False)  # code
        size = reader.read_int()
        for _ in range(size):
            inner_msg_id = reader.read_long()
            inner_sequence = reader.read_int()
            inner_length = reader.read_int()
            yield inner_msg_id, inner_sequence, inner_length
