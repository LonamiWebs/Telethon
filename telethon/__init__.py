# Note: the import order matters
from ._misc import helpers as _  # no dependencies
from . import _tl  # no dependencies
from ._misc import utils as _  # depends on helpers and _tl
from ._misc import hints as _  # depends on types/custom
from ._client.account import ignore_takeout

from ._client.telegramclient import TelegramClient
from . import version, events, errors, enums

__version__ = version.__version__
