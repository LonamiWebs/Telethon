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
        303: rpc_errors_303_all,
        400: rpc_errors_400_all,
        401: rpc_errors_401_all,
        420: rpc_errors_420_all
    }.get(code, None)

    if errors is not None:
        for msg, cls in errors.items():
            m = re.match(msg, message)
            if m:
                extra = int(m.group(1)) if m.groups() else None
                return cls(extra=extra)

    elif code == 403:
        return ForbiddenError(message)

    elif code == 404:
        return NotFoundError(message)

    elif code == 500:
        return ServerError(message)

    return RPCError('{} (code {})'.format(message, code))
