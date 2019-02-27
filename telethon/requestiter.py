import abc
import asyncio
import time


# TODO There are two types of iterators for requests.
#      One has a limit of items to retrieve, and the
#      other has a list that must be called in chunks.
#      Make classes for both here so it's easy to use.
class RequestIter(abc.ABC):
    """
    Helper class to deal with requests that need offsets to iterate.

    It has some facilities, such as automatically sleeping a desired
    amount of time between requests if needed (but not more).

    Can be used synchronously if the event loop is not running and
    as an asynchronous iterator otherwise.

    `limit` is the total amount of items that the iterator should return.
    This is handled on this base class, and will be always ``>= 0``.

    `left` will be reset every time the iterator is used and will indicate
    the amount of items that should be emitted left, so that subclasses can
    be more efficient and fetch only as many items as they need.

    Iterators may be used with ``reversed``, and their `reverse` flag will
    be set to ``True`` if that's the case. Note that if this flag is set,
    `buffer` should be filled in reverse too.
    """
    def __init__(self, client, limit, *, reverse=False, wait_time=None, **kwargs):
        self.client = client
        self.reverse = reverse
        self.wait_time = wait_time
        self.kwargs = kwargs
        self.limit = max(float('inf') if limit is None else limit, 0)
        self.left = None
        self.buffer = None
        self.index = None
        self.total = None
        self.last_load = None

    async def _init(self, **kwargs):
        """
        Called when asynchronous initialization is necessary. All keyword
        arguments passed to `__init__` will be forwarded here, and it's
        preferable to use named arguments in the subclasses without defaults
        to avoid forgetting or misspelling any of them.

        This method may ``raise StopAsyncIteration`` if it cannot continue.

        This method may actually fill the initial buffer if it needs to.
        """

    async def __anext__(self):
        if self.buffer is ():
            await self._init(**self.kwargs)

        if self.left <= 0:  # <= 0 because subclasses may change it
            raise StopAsyncIteration

        if self.index == len(self.buffer):
            # asyncio will handle times <= 0 to sleep 0 seconds
            if self.wait_time:
                await asyncio.sleep(
                    self.wait_time - (time.time() - self.last_load),
                    loop=self.client.loop
                )
                self.last_load = time.time()

            self.index = 0
            self.buffer = await self._load_next_chunk()

        if not self.buffer:
            raise StopAsyncIteration

        result = self.buffer[self.index]
        self.left -= 1
        self.index += 1
        return result

    def __aiter__(self):
        self.buffer = ()
        self.index = 0
        self.last_load = 0
        self.left = self.limit
        return self

    def __iter__(self):
        if self.client.loop.is_running():
            raise RuntimeError(
                'You must use "async for" if the event loop '
                'is running (i.e. you are inside an "async def")'
            )

        return self.__aiter__()

    @abc.abstractmethod
    async def _load_next_chunk(self):
        """
        Called when the next chunk is necessary.
        It should *always* return a `list`.
        """
        raise NotImplementedError

    def __reversed__(self):
        self.reverse = not self.reverse
        return self  # __aiter__ will be called after, too
