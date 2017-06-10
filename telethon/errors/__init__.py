import re

from .common import (
    ReadCancelledError, InvalidParameterError, TypeNotFoundError,
    InvalidChecksumError
)

from .rpc_errors import (
    RPCError, InvalidDCError, BadRequestError, UnauthorizedError,
    ForbiddenError, NotFoundError, FloodError, ServerError, BadMessageError
)

from .rpc_errors_303 import *
from .rpc_errors_400 import *
from .rpc_errors_401 import *
from .rpc_errors_420 import *


def rpc_message_to_error(code, message):
    errors = {
        303: rpc_303_errors,
        400: rpc_400_errors,
        401: rpc_401_errors,
        420: rpc_420_errors
    }.get(code, None)

    if errors is not None:
        for msg, cls in errors.items():
            m = re.match(msg, message)
            if m:
                extra = int(m.group(1)) if m.groups() else None
                return cls(extra=extra)

    elif code == 403:
        return ForbiddenError()

    elif code == 404:
        return NotFoundError()

    elif code == 500:
        return ServerError()

    return RPCError('{} (code {})'.format(message, code))
