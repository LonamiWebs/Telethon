from . import TLObject, GzipPacked
from ..extensions import BinaryWriter


class MessageContainer(TLObject):
    constructor_id = 0x73f1f8dc

    # TODO Currently it's a bit of a hack, since the container actually holds
    # messages (message id, sequence number, request body), not requests.
    # Probably create a proper "Message" class
    def __init__(self, session, requests):
        super().__init__()
        self.content_related = False
        self.session = session
        self.requests = requests

    def to_bytes(self):
        # TODO Change this to delete the on_send from this class
        with BinaryWriter() as writer:
            writer.write_int(MessageContainer.constructor_id, signed=False)
            writer.write_int(len(self.requests))
            for x in self.requests:
                x.request_msg_id = self.session.get_new_msg_id()

                writer.write_long(x.request_msg_id)
                writer.write_int(
                    self.session.generate_sequence(x.content_related)
                )

                packet = GzipPacked.gzip_if_smaller(x)
                writer.write_int(len(packet))
                writer.write(packet)
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
