from ._custom import (
    ReadCancelledError,
    TypeNotFoundError,
    InvalidChecksumError,
    InvalidBufferError,
    SecurityError,
    CdnFileTamperedError,
    BadMessageError,
    MultiError,
    SignUpRequired,
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

# https://www.python.org/dev/peps/pep-0562/
def __getattr__(name):
    return _mk_error_type(name=name)
