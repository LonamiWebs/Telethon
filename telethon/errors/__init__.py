import sys

from ._custom import (
    ReadCancelledError,
    TypeNotFoundError,
    InvalidChecksumError,
    InvalidBufferError,
    SecurityError,
    CdnFileTamperedError,
    BadMessageError,
    MultiError,
)
from ._rpcbase import (
    RpcError,
    InvalidDcError,
    BadRequestError,
    UnauthorizedError,
    ForbiddenError,
    NotFoundError,
    AuthKeyError,
    FloodError,
    ServerError,
    BotTimeout,
    TimedOutError,
    _mk_error_type
)

if sys.version_info < (3, 7):
    # https://stackoverflow.com/a/7668273/
    class _TelethonErrors:
        def __init__(self, _mk_error_type, everything):
            self._mk_error_type = _mk_error_type
            self.__dict__.update({
                k: v
                for k, v in everything.items()
                if isinstance(v, type) and issubclass(v, Exception)
            })

        def __getattr__(self, name):
            return self._mk_error_type(name=name)

    sys.modules[__name__] = _TelethonErrors(_mk_error_type, globals())
else:
    # https://www.python.org/dev/peps/pep-0562/
    def __getattr__(name):
        return _mk_error_type(name=name)

del sys
