from . import (
    UpdateMethods, AuthMethods, DownloadMethods, DialogMethods,
    ChatMethods, MessageMethods, UploadMethods, MessageParseMethods,
    UserMethods
)


class TelegramClient(
    UpdateMethods, AuthMethods, DownloadMethods, DialogMethods,
    ChatMethods, MessageMethods, UploadMethods, MessageParseMethods,
    UserMethods
):
    pass
