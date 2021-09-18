# Note: the import order matters
from ._misc import helpers  # no dependencies
from . import _tl  # no dependencies
from ._misc import utils  # depends on helpers and _tl
from ._misc import hints  # depends on types/custom

from ._client.telegramclient import TelegramClient
from . import version, events, utils, errors, enums

__version__ = version.__version__
