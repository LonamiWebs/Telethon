from requests.mtproto_request import MTProtoRequest


class AckRequest(MTProtoRequest):
    def __init__(self, msgs):
        super().__init__()
        self.msgs = msgs

    def on_send(self, writer):
        writer.write_int(0x62d6b459)  # msgs_ack
        writer.write_int(0x1cb5c415)  # vector
        writer.write_int(len(self.msgs))
        for msg_id in self.msgs:
            writer.write_int(msg_id, signed=False)

    def on_response(self, reader):
        pass

    def on_exception(self, exception):
        pass
