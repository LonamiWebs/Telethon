import asyncio


class RequestState:
    """
    This request state holds several information relevant to sent messages,
    in particular the message ID assigned to the request, the container ID
    it belongs to, the request itself, the request as bytes, and the future
    result that will eventually be resolved.
    """
    __slots__ = ('container_id', 'msg_id', 'request', 'data', 'future', 'after')

    def __init__(self, request, loop, after=None):
        self.container_id = None
        self.msg_id = None
        self.request = request
        self.data = bytes(request)
        self.future = asyncio.Future(loop=loop)
        self.after = after
