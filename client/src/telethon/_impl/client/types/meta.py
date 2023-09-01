from typing import Type, TypeVar

T = TypeVar("T")


class NoPublicConstructor(type):
    def __call__(cls, *args: object, **kwargs: object) -> None:
        raise TypeError(
            f"{cls.__module__}.{cls.__qualname__} has no public constructor"
        )

    @property
    def _create(cls: Type[T]) -> Type[T]:
        return super().__call__  # type: ignore
