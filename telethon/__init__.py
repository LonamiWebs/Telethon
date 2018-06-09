import logging
from .client.telegramclient import TelegramClient
from .network import connection
from . import tl, version


__version__ = version.__version__
logging.getLogger(__name__).addHandler(logging.NullHandler())
