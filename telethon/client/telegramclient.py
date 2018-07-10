from . import (
    AuthMethods, DownloadMethods, DialogMethods, ChatMethods,
    MessageMethods, ButtonMethods, UpdateMethods, UploadMethods,
    MessageParseMethods, UserMethods
)


class TelegramClient(
    AuthMethods, DownloadMethods, DialogMethods, ChatMethods,
    MessageMethods, UploadMethods, ButtonMethods, UpdateMethods,
    MessageParseMethods, UserMethods
):
    pass
