import abc
from collections import deque
from collections.abc import Generator
from typing import Any, Generic, TypeVar

from typing_extensions import Self

T = TypeVar("T")


class AsyncList(abc.ABC, Generic[T]):
    """
    An asynchronous list.

    It can be awaited to get all the items as a normal :class:`list`,
    or iterated over via `async for <https://docs.python.org/3/reference/compound_stmts.html#the-async-for-statement>`_.

    Both approaches will perform as many requests as needed to retrieve the
    items, but awaiting will need to do it all at once, which can be slow.

    Using asynchronous iteration will perform the requests lazily as needed,
    and lets you break out of the loop at any time to stop fetching items.

    The :func:`len` of the asynchronous list will be the "total count" reported
    by the server. It does not necessarily reflect how many items will
    actually be returned. This count can change as more items are fetched.
    Note that this method cannot be awaited.

    .. rubric:: Example

    :meth:`telethon.Client.get_messages` returns an :class:`AsyncList`\\ [:class:`Message`].
    This means:

    .. code-block:: python

        # You can await it directly:
        messages = await client.get_messages(chat, 1)
        # ...and now messages is a normal list with a single Message.

        # Or you can use async for:
        async for mesasge in client.get_messages(chat, 1):
            ...  # the messages are fetched lazily, rather than all up-front.
    """

    def __init__(self) -> None:
        self._buffer: deque[T] = deque()
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

    async def _collect(self) -> list[T]:
        prev = -1
        while not self._done and prev != len(self._buffer):
            prev = len(self._buffer)
            await self._fetch_next()
        return list(self._buffer)

    def __await__(self) -> Generator[Any, None, list[T]]:
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
