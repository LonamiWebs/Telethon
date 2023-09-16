class ErrorFactory:
    __slots__ = ()

    def __getattribute__(self, name: str) -> ValueError:
        raise NotImplementedError


errors = ErrorFactory()
