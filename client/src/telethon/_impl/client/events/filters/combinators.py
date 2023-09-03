from typing import Tuple

from ..event import Event
from .common import Filter


class Any:
    """
    Combine multiple filters, returning `True` if any of the filters pass.
    """

    __slots__ = ("_filters",)

    def __init__(self, filter1: Filter, filter2: Filter, *filters: Filter) -> None:
        self._filters = (filter1, filter2, *filters)

    @property
    def filters(self) -> Tuple[Filter, ...]:
        """
        The filters being checked, in order.
        """
        return self._filters

    def __call__(self, event: Event) -> bool:
        return any(f(event) for f in self._filters)


class All:
    """
    Combine multiple filters, returning `True` if all of the filters pass.
    """

    __slots__ = ("_filters",)

    def __init__(self, filter1: Filter, filter2: Filter, *filters: Filter) -> None:
        self._filters = (filter1, filter2, *filters)

    @property
    def filters(self) -> Tuple[Filter, ...]:
        """
        The filters being checked, in order.
        """
        return self._filters

    def __call__(self, event: Event) -> bool:
        return all(f(event) for f in self._filters)


class Not:
    """
    Negate the output of a single filter, returning `True` if the nested
    filter does *not* pass.
    """

    __slots__ = ("_filter",)

    def __init__(self, filter: Filter) -> None:
        self._filter = filter

    @property
    def filter(self) -> Filter:
        """
        The filters being negated.
        """
        return self._filter

    def __call__(self, event: Event) -> bool:
        return not self._filter(event)
