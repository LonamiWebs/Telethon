import logging
from .client.telegramclient import TelegramClient
from .network import connection
from .tl import types, functions, custom
from . import version, events, utils, errors


__version__ = version.__version__
logging.getLogger(__name__).addHandler(logging.NullHandler())

__all__ = ['TelegramClient', 'types', 'functions', 'custom',
           'events', 'utils', 'errors']
