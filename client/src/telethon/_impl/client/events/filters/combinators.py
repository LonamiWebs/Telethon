import abc
from collections.abc import Callable
from inspect import isawaitable
from typing import Awaitable, TypeAlias

from ..event import Event

FilterType: TypeAlias = "Callable[[Event], bool | Awaitable[bool]] | Combinable"


class Combinable(abc.ABC):
    """
    Subclass that enables filters to be combined.

    * The :func:`bitwise or <operator.or_>` operator ``|`` can be used to combine filters with :class:`Any`.
    * The :func:`bitwise and <operator.and_>` operator ``&`` can be used to combine filters with :class:`All`.
    * The :func:`bitwise invert <operator.invert>` operator ``~`` can be used to negate a filter with :class:`Not`.

    Filters combined this way will be merged.
    This means multiple ``|`` or ``&`` will lead to a single :class:`Any` or :class:`All` being used.
    Multiple ``~`` will toggle between using :class:`Not` and not using it.
    """

    def __or__(self, other: FilterType) -> "Any":
        lhs = self.filters if isinstance(self, Any) else (self,)
        rhs = other.filters if isinstance(other, Any) else (other,)
        return Any(*lhs, *rhs)

    def __and__(self, other: FilterType) -> "All":
        lhs = self.filters if isinstance(self, All) else (self,)
        rhs = other.filters if isinstance(other, All) else (other,)
        return All(*lhs, *rhs)

    def __invert__(self) -> "Not | FilterType":
        return self.filter if isinstance(self, Not) else Not(self)

    @abc.abstractmethod
    async def __call__(self, event: Event) -> bool:
        pass


class Any(Combinable):
    """
    Combine multiple filters, returning :data:`True` if any of the filters pass.

    When either filter is :class:`~telethon._impl.client.events.filters.combinators.Combinable`,
    you can use the ``|`` operator instead.

    .. code-block:: python

        from telethon.events.filters import Any, Command

        @bot.on(events.NewMessage, Any(Command('/start'), Command('/help')))
        async def handler(event): ...

        # equivalent to:

        @bot.on(events.NewMessage, Command('/start') | Command('/help'))
        async def handler(event): ...

    :param filter1: The first filter to check.
    :param filter2: The second filter to check if the first one failed.
    :param filters: The rest of filters to check if the first and second one failed.
    """

    __slots__ = ("_filters",)

    def __init__(
        self, filter1: FilterType, filter2: FilterType, *filters: FilterType
    ) -> None:
        self._filters = (filter1, filter2, *filters)

    @property
    def filters(self) -> tuple[FilterType, ...]:
        """
        The filters being checked, in order.
        """
        return self._filters

    async def __call__(self, event: Event) -> bool:
        for f in self._filters:
            if await r if isawaitable(r := f(event)) else r:
                return True

        return False


class All(Combinable):
    """
    Combine multiple filters, returning :data:`True` if all of the filters pass.

    When either filter is :class:`~telethon._impl.client.events.filters.combinators.Combinable`,
    you can use the ``&`` operator instead.

    .. code-block:: python

        from telethon.events.filters import All, Command, Text

        @bot.on(events.NewMessage, All(Command('/start'), Text(r'\\bdata:\\w+')))
        async def handler(event): ...

        # equivalent to:

        @bot.on(events.NewMessage, Command('/start') & Text(r'\\bdata:\\w+'))
        async def handler(event): ...

    :param filter1: The first filter to check.
    :param filter2: The second filter to check.
    :param filters: The rest of filters to check.
    """

    __slots__ = ("_filters",)

    def __init__(
        self, filter1: FilterType, filter2: FilterType, *filters: FilterType
    ) -> None:
        self._filters = (filter1, filter2, *filters)

    @property
    def filters(self) -> tuple[FilterType, ...]:
        """
        The filters being checked, in order.
        """
        return self._filters

    async def __call__(self, event: Event) -> bool:
        for f in self._filters:
            if not (await r if isawaitable(r := f(event)) else r):
                return False

        return True


class Not(Combinable):
    """
    Negate the output of a single filter, returning :data:`True` if the nested filter does *not* pass.

    When the filter is :class:`~telethon._impl.client.events.filters.combinators.Combinable`,
    you can use the ``~`` operator instead.

    .. code-block:: python

        from telethon.events.filters import All, Command

        @bot.on(events.NewMessage, Not(Command('/start'))
        async def handler(event): ...

        # equivalent to:

        @bot.on(events.NewMessage, ~Command('/start'))
        async def handler(event): ...

    :param filter: The filter to negate.
    """

    __slots__ = ("_filter",)

    def __init__(self, filter: FilterType) -> None:
        self._filter = filter

    @property
    def filter(self) -> FilterType:
        """
        The filter being negated.
        """
        return self._filter

    async def __call__(self, event: Event) -> bool:
        return not (await r if isawaitable(r := self._filter(event)) else r)
