from ._client.telegramclient import TelegramClient
from .network import connection
from ._tl import custom
from ._tl.custom import Button
from . import version, events, utils, errors

__version__ = version.__version__

__all__ = [
    'TelegramClient', 'Button',
    'types', 'functions', 'custom', 'errors',
    'events', 'utils', 'connection'
]
