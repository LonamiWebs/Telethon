import os
# Only import most stuff if the TLObjects were generated and there were no errors
if os.path.isfile('tl/all_tlobjects.py'):
    try:
        from .all_tlobjects import tlobjects
        from .session import Session
        from .mtproto_request import MTProtoRequest
        from .telegram_client import TelegramClient
    except Exception:
        print('Please fix `tl_generator.py` and run it again')
else:
    print('Please run `python3 tl_generator.py` first')
del os
from .tlobject import TLObject, TLArg
