"""
This module holds all the base and automatically generated errors that the
Telegram API has. See telethon_generator/errors.json for more.
"""
import urllib.request
import re
from threading import Thread

from .common import (
    ReadCancelledError, TypeNotFoundError, InvalidChecksumError,
    BrokenAuthKeyError, SecurityError, CdnFileTamperedError
)

# This imports the base errors too, as they're imported there
from .rpcbaseerrors import *
from .rpcerrorlist import *


def report_error(code, message, report_method):
    """
    Reports an RPC error to pwrtelegram.

    :param code: the integer code of the error (like 400).
    :param message: the message representing the error.
    :param report_method: the constructor ID of the function that caused it.
    """
    try:
        # Ensure it's signed
        report_method = int.from_bytes(
            report_method.to_bytes(4, 'big'), 'big', signed=True
        )
        url = urllib.request.urlopen(
            'https://rpc.pwrtelegram.xyz?code={}&error={}&method={}'
            .format(code, message, report_method),
            timeout=5
        )
        url.read()
        url.close()
    except Exception as e:
        "We really don't want to crash when just reporting an error"


def rpc_message_to_error(rpc_error, report_method=None):
    """
    Converts a Telegram's RPC Error to a Python error.

    :param rpc_error: the RpcError instance.
    :param report_method: if present, the ID of the method that caused it.
    :return: the RPCError as a Python exception that represents this error.
    """
    if report_method is not None:
        Thread(
            target=report_error,
            args=(rpc_error.error_code, rpc_error.error_message, report_method)
        ).start()

    # Try to get the error by direct look-up, otherwise regex
    cls = rpc_errors_dict.get(rpc_error.error_message, None)
    if cls:
        return cls()

    for msg_regex, cls in rpc_errors_re:
        m = re.match(msg_regex, rpc_error.error_message)
        if m:
            capture = int(m.group(1)) if m.groups() else None
            return cls(capture=capture)

    cls = base_errors.get(rpc_error.error_code, RPCError)
    return cls(rpc_error.error_message)
