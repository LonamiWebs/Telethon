from . import (
    AccountMethods, AuthMethods, DownloadMethods, DialogMethods, ChatMethods,
    BotMethods, MessageMethods, UploadMethods, ButtonMethods, UpdateMethods,
    MessageParseMethods, UserMethods, TelegramBaseClient, SecretChatMethods
)


class TelegramClient(
    AccountMethods, AuthMethods, DownloadMethods, DialogMethods, ChatMethods,
    BotMethods, MessageMethods, UploadMethods, ButtonMethods, UpdateMethods,
    MessageParseMethods, UserMethods, TelegramBaseClient, SecretChatMethods
):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
