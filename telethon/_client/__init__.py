"""
This package defines clients as subclasses of others, and then a single
`telethon.client.telegramclient.TelegramClient` which is subclass of them
all to provide the final unified interface while the methods can live in
different subclasses to be more maintainable.

The ABC is `telethon.client.telegrambaseclient.TelegramBaseClient` and the
first implementor is `telethon.client.users.UserMethods`, since calling
requests require them to be resolved first, and that requires accessing
entities (users).
"""
from .telegrambaseclient import TelegramBaseClient
from .users import UserMethods  # Required for everything
from .messageparse import MessageParseMethods  # Required for messages
from .uploads import UploadMethods  # Required for messages to send files
from .updates import UpdateMethods  # Required for buttons (register callbacks)
from .buttons import ButtonMethods  # Required for messages to use buttons
from .messages import MessageMethods
from .chats import ChatMethods
from .dialogs import DialogMethods
from .downloads import DownloadMethods
from .account import AccountMethods
from .auth import AuthMethods
from .bots import BotMethods
from .telegramclient import TelegramClient
