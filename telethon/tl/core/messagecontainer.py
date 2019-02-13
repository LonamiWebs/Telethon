from .tlmessage import TLMessage
from ..tlobject import TLObject


class MessageContainer(TLObject):
    CONSTRUCTOR_ID = 0x73f1f8dc

    # Maximum size in bytes for the inner payload of the container.
    # Telegram will close the connection if the payload is bigger.
    # The overhead of the container itself is subtracted.
    MAXIMUM_SIZE = 1044456 - 8

    # Maximum amount of messages that can't be sent inside a single
    # container, inclusive. Beyond this limit Telegram will respond
    # with BAD_MESSAGE 64 (invalid container).
    #
    # This limit is not 100% accurate and may in some cases be higher.
    # However, sending up to 100 requests at once in a single container
    # is a reasonable conservative value, since it could also depend on
    # other factors like size per request, but we cannot know this.
    MAXIMUM_LENGTH = 100

    def __init__(self, messages):
        self.messages = messages

    def to_dict(self):
        return {
            '_': 'MessageContainer',
            'messages':
                [] if self.messages is None else [
                    None if x is None else x.to_dict() for x in self.messages
                ],
        }

    @classmethod
    def from_reader(cls, reader):
        # This assumes that .read_* calls are done in the order they appear
        messages = []
        for _ in range(reader.read_int()):
            msg_id = reader.read_long()
            seq_no = reader.read_int()
            length = reader.read_int()
            before = reader.tell_position()
            obj = reader.tgread_object()  # May over-read e.g. RpcResult
            reader.set_position(before + length)
            messages.append(TLMessage(msg_id, seq_no, obj))
        return MessageContainer(messages)
