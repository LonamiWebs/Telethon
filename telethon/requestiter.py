import abc
import asyncio
import time

from . import helpers


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
        self.left = self.limit
        self.buffer = None
        self.index = 0
        self.total = None
        self.last_load = 0

    async def _init(self, **kwargs):
        """
        Called when asynchronous initialization is necessary. All keyword
        arguments passed to `__init__` will be forwarded here, and it's
        preferable to use named arguments in the subclasses without defaults
        to avoid forgetting or misspelling any of them.

        This method may ``raise StopAsyncIteration`` if it cannot continue.

        This method may actually fill the initial buffer if it needs to,
        and similarly to `_load_next_chunk`, ``return True`` to indicate
        that this is the last iteration (just the initial load).
        """

    async def __anext__(self):
        if self.buffer is None:
            self.buffer = []
            if await self._init(**self.kwargs):
                self.left = len(self.buffer)

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
            self.buffer = []
            if await self._load_next_chunk():
                self.left = len(self.buffer)

        if not self.buffer:
            raise StopAsyncIteration

        result = self.buffer[self.index]
        self.left -= 1
        self.index += 1
        return result

    def __next__(self):
        try:
            return self.client.loop.run_until_complete(self.__anext__())
        except StopAsyncIteration:
            raise StopIteration

    def __aiter__(self):
        self.buffer = None
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

    async def collect(self):
        """
        Create a `self` iterator and collect it into a `TotalList`
        (a normal list with a `.total` attribute).
        """
        result = helpers.TotalList()
        async for message in self:
            result.append(message)

        result.total = self.total
        return result

    @abc.abstractmethod
    async def _load_next_chunk(self):
        """
        Called when the next chunk is necessary.

        It should extend the `buffer` with new items.

        It should return ``True`` if it's the last chunk,
        after which moment the method won't be called again
        during the same iteration.
        """
        raise NotImplementedError

    def __reversed__(self):
        self.reverse = not self.reverse
        return self  # __aiter__ will be called after, too
