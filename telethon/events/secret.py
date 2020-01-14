from .common import EventBuilder, EventCommon, name_inner_event
from ..tl import types


@name_inner_event
class SecretChat(EventBuilder):
    def __init__(self, to_finish=False, to_accept=False, to_decrypt=False):
        self.to_finish = to_finish
        self.to_accept = to_accept
        self.to_decrypt = to_decrypt
        super().__init__()

    @classmethod
    def build(cls, update, others=None, self_id=None):
        if isinstance(update, types.UpdateEncryption):
            if isinstance(update.chat, types.EncryptedChat):
                return cls.Event(update,
                                 to_finish=True)
            elif isinstance(update.chat, types.EncryptedChatRequested):
                return cls.Event(update, to_accept=True)
        elif isinstance(update, types.UpdateNewEncryptedMessage):
            return cls.Event(update, to_decrypt=True)

    class Event(EventCommon):
        def __init__(self, update, to_finish=False, to_accept=False, to_decrypt=False):
            if isinstance(update, types.UpdateEncryption):
                super().__init__(chat_peer=update.chat)
            else:
                super().__init__(chat_peer=update.message.chat_id)
            self.original_update = update
            self.to_finish = to_finish
            self.to_accept = to_accept
            self.to_decrypt = to_decrypt
            self.decrypted_message = None

        def _set_client(self, client):
            self._chat_peer = None
            super()._set_client(client)

        async def finish(self):
            return await self._client.finish_secret_chat_creation(self.original_update.chat)

        async def accept(self):
            return await self._client.accept_secret_chat(self.original_update.chat)

        async def decrypt(self):
            self.decrypted_message = await self._client.handle_encrypted_update(self.original_update)
            return self.decrypted_message

        async def reply(self, message, ttl=0):
            if not self.decrypted_message:
                await self.decrypt()
            return await self._client.send_secret_message(self.original_update.message.chat_id, message, ttl,
                                                          self.decrypted_message.random_id)

        async def respond(self, message, ttl=0):
            return await self._client.send_secret_message(self.original_update.message.chat_id, message, ttl)

            pass

    def filter(self, event):
        event = event.original_update
        if isinstance(event, types.UpdateEncryption):
            if isinstance(event.chat, types.EncryptedChat):
                if not self.to_finish:
                    return
            elif isinstance(event.chat, types.EncryptedChatRequested):
                if not self.to_accept:
                    return
        elif isinstance(event, types.UpdateNewEncryptedMessage):
            if not self.to_decrypt:
                return

        return super().filter(event)
