from . import FloodError


class FloodWaitError(FloodError):
    def __init__(self, **kwargs):
        self.seconds = kwargs['extra']
        super(Exception, self).__init__(
            self,
            'A wait of {} seconds is required.'
            .format(self.seconds)
        )


rpc_420_errors = {
    'FLOOD_WAIT_(\d+)': FloodWaitError
}
