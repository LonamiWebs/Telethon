"""
The main package for the Telethon library.
"""

from ._impl import tl as _tl
from ._impl.client import Client
from ._impl.client.errors import errors
from ._impl.mtproto import RpcError
from .version import __version__

__all__ = ["_tl", "Client", "errors", "RpcError", "__version__"]
