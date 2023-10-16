"""
Class definitions stolen from `trio`, with some modifications.
"""
import abc
from typing import Type, TypeVar

T = TypeVar("T")


class Final(abc.ABCMeta):
    def __new__(
        cls,
        name: str,
        bases: tuple[type, ...],
        cls_namespace: dict[str, object],
    ) -> "Final":
        # Allow subclassing while within telethon._impl (or other package names).
        allowed_base = Final.__module__[
            : Final.__module__.find(".", Final.__module__.find(".") + 1)
        ]
        for base in bases:
            if isinstance(base, Final) and not base.__module__.startswith(allowed_base):
                raise TypeError(
                    f"{base.__module__}.{base.__qualname__} does not support"
                    " subclassing"
                )
        return super().__new__(cls, name, bases, cls_namespace)


class NoPublicConstructor(Final):
    def __call__(cls) -> None:
        raise TypeError(
            f"{cls.__module__}.{cls.__qualname__} has no public constructor"
        )

    @property
    def _create(cls: Type[T]) -> Type[T]:
        return super().__call__  # type: ignore
