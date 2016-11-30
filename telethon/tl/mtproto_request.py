from datetime import datetime, timedelta


class MTProtoRequest:
    def __init__(self):
        self.sent = False

        self.msg_id = 0  # Long
        self.sequence = 0

        self.dirty = False
        self.send_time = None
        self.confirm_received = False

        # These should be overrode
        self.constructor_id = 0
        self.confirmed = False
        self.responded = False

    # These should not be overrode
    def on_send_success(self):
        self.send_time = datetime.now()
        self.sent = True

    def on_confirm(self):
        self.confirm_received = True

    def need_resend(self):
        return self.dirty or (
            self.confirmed and not self.confirm_received and
            datetime.now() - self.send_time > timedelta(seconds=3))

    # These should be overrode
    def on_send(self, writer):
        pass

    def on_response(self, reader):
        pass

    def on_exception(self, exception):
        pass
