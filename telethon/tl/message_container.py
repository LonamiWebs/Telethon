import struct

from . import TLObject


class MessageContainer(TLObject):
    CONSTRUCTOR_ID = 0x73f1f8dc

    def __init__(self, messages):
        super().__init__()
        self.content_related = False
        self.messages = messages

    def to_dict(self, recursive=True):
        return {
            'content_related': self.content_related,
            'messages':
                ([] if self.messages is None else [
                    None if x is None else x.to_dict() for x in self.messages
                ]) if recursive else self.messages,
        }

    def __bytes__(self):
        return struct.pack(
            '<Ii', MessageContainer.CONSTRUCTOR_ID, len(self.messages)
        ) + b''.join(bytes(m) for m in self.messages)

    @staticmethod
    def iter_read(reader):
        reader.read_int(signed=False)  # code
        size = reader.read_int()
        for _ in range(size):
            inner_msg_id = reader.read_long()
            inner_sequence = reader.read_int()
            inner_length = reader.read_int()
            yield inner_msg_id, inner_sequence, inner_length

    def __str__(self):
        return TLObject.pretty_format(self)

    def stringify(self):
        return TLObject.pretty_format(self, indent=0)
