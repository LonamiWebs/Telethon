import abc


class Filter(abc.ABC):
    @abc.abstractmethod
    def __call__(self, event):
        return True

    def __and__(self, other):
        return And(self, other)

    def __or__(self, other):
        return Or(self, other)

    def __invert__(self):
        return Not(self)


class And(Filter):
    """
    All underlying filters must return `True` for this filter to be `True`.
    """
    def __init__(self, *filters):
        self._filters = filters

    def __call__(self, event):
        return all(f(event) for f in self._filters)


class Or(Filter):
    """
    At least one underlying filter must return `True` for this filter to be `True`.
    """
    def __init__(self, *filters):
        self._filters = filters

    def __call__(self, event):
        return any(f(event) for f in self._filters)


class Not(Filter):
    """
    The underlying filter must return `False` for this filter to be `True`.
    """
    def __init__(self, filter):
        self._filter = filter

    def __call__(self, event):
        return not self._filter(event)


class Identity(Filter):
    """
    Return the value of the underlying filter (or callable) without any modifications.
    """
    def __init__(self, filter):
        self._filter = filter

    def __call__(self, event):
        return self._filter(event)


class Always(Filter):
    """
    This filter always returns `True`, and is used as the "empty filter".
    """
    def __call__(self, event):
        return True


class Never(Filter):
    """
    This filter always returns `False`, and is used when an impossible filter is made
    (for example, neither outgoing nor incoming is always false). This can be used to
    "turn off" handlers without removing them.
    """
    def __call__(self, event):
        return False
