import abc
from collections import deque
from typing import Any, Deque, Generator, Generic, List, Self, TypeVar

T = TypeVar("T")


class AsyncList(abc.ABC, Generic[T]):
    """
    An asynchronous list.

    It can be awaited to get all the items as a normal `list`,
    or iterated over via `async for`.

    Both approaches will perform as many requests as needed to retrieve the
    items, but awaiting will need to do it all at once, which can be slow.

    Using asynchronous iteration will perform the requests lazily as needed,
    and lets you break out of the loop at any time to stop fetching items.

    The `len()` of the asynchronous list will be the "total count" reported
    by the server. It does not necessarily reflect how many items will
    actually be returned. This count can change as more items are fetched.
    Note that this method cannot be awaited.
    """

    def __init__(self) -> None:
        self._buffer: Deque[T] = deque()
        self._total: int = 0
        self._done = False

    @abc.abstractmethod
    async def _fetch_next(self) -> None:
        """
        Fetch the next chunk of items.

        The `_buffer` should be extended from the end, not the front.
        The `_total` should be updated with the count reported by the server.
        The `_done` flag should be set if it is known that the end was reached
        """

    async def _collect(self) -> List[T]:
        prev = -1
        while not self._done and prev != len(self._buffer):
            prev = len(self._buffer)
            await self._fetch_next()
        return list(self._buffer)

    def __await__(self) -> Generator[Any, None, List[T]]:
        return self._collect().__await__()

    def __aiter__(self) -> Self:
        return self

    async def __anext__(self) -> T:
        if not self._buffer:
            if self._done:
                raise StopAsyncIteration
            await self._fetch_next()

        if not self._buffer:
            self._done = True
            raise StopAsyncIteration

        return self._buffer.popleft()

    def __len__(self) -> int:
        return self._total
