from . import (
    AccountMethods, AuthMethods, DownloadMethods, DialogMethods, ChatMethods,
    BotMethods, MessageMethods, UploadMethods, ButtonMethods, UpdateMethods,
    MessageParseMethods, UserMethods
)


class TelegramClient(
    AccountMethods, AuthMethods, DownloadMethods, DialogMethods, ChatMethods,
    BotMethods, MessageMethods, UploadMethods, ButtonMethods, UpdateMethods,
    MessageParseMethods, UserMethods
):
    pass
