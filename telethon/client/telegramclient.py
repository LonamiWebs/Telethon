from . import (
    AuthMethods, DownloadMethods, DialogMethods, ChatMethods, BotMethods,
    MessageMethods, ButtonMethods, UpdateMethods, UploadMethods,
    MessageParseMethods, UserMethods
)


class TelegramClient(
    AuthMethods, DownloadMethods, DialogMethods, ChatMethods, BotMethods,
    MessageMethods, UploadMethods, ButtonMethods, UpdateMethods,
    MessageParseMethods, UserMethods
):
    pass
