import os
# Only import most stuff if the TLObjects were generated
if os.path.isfile('tl/all_tlobjects.py'):
    from .all_tlobjects import tlobjects
    from .session import Session
    from .mtproto_request import MTProtoRequest
    from .telegram_client import TelegramClient
del os
from .tlobject import TLObject, TLArg
