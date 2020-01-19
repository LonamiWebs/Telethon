import hashlib
import random
from hashlib import sha1, sha256, md5
from time import time

from .. import utils
from ..crypto import AES
from ..errors import SecurityError, EncryptionAlreadyDeclinedError
from ..extensions import BinaryReader
from ..network.mtprotostate import MTProtoState
from ..tl.functions.messages import AcceptEncryptionRequest, SendEncryptedFileRequest
from ..tl.functions.messages import GetDhConfigRequest, RequestEncryptionRequest, SendEncryptedServiceRequest, \
    DiscardEncryptionRequest, SendEncryptedRequest
from ..tl.types import InputEncryptedChat, TypeEncryptedChat, EncryptedFile, InputEncryptedFileLocation, \
    InputEncryptedFile, InputFileBig, InputFile, InputEncryptedFileBigUploaded, InputEncryptedFileUploaded
from ..tl.types.messages import DhConfigNotModified
from ..tl.types.secret import *

DEFAULT_LAYER = 101


class ChatKey:
    def __init__(self, auth_key: bytes):
        self.auth_key = auth_key
        self.fingerprint = None


class Chats:
    def __init__(self, id: int, access_hash: int, key: ChatKey, admin: bool, user_id: int,
                 input_chat: InputEncryptedChat):
        self.id = id
        self.access_hash = access_hash
        self.key = key
        self.admin = admin
        self.user_id = user_id
        self.input_chat = input_chat
        self.in_seq_no_x = 0 if admin else 1
        self.out_seq_no_x = 1 if admin else 0
        self.in_seq_no = 0
        self.out_seq_no = 0
        self.layer = DEFAULT_LAYER
        self.ttl = 0
        self.ttr = 100
        self.updated = time()
        self.incoming = {}
        self.outgoing = {}
        self.created = time()
        self.rekeying = [0]
        self.mtproto = 1


class SecretChatMethods:

    def get_secret_chat(self, chat_id) -> Chats:
        if isinstance(chat_id, int):
            peer = self.secret_chats.get(chat_id, None)
            if not peer:
                raise ValueError("chat not found")
            return peer
        try:
            peer = self.secret_chats.get(chat_id.id, None)
            if not peer:
                raise ValueError("chat not found")
            return peer
        except AttributeError:
            pass
        try:
            peer = self.secret_chats.get(chat_id.chat_id, None)
            if not peer:
                raise ValueError("chat not found")
            return peer
        except AttributeError:
            pass
        raise ValueError("chat not found")

    async def get_dh_config(self):
        version = 0 if not self.dh_config else self.dh_config.version
        dh_config = await self(GetDhConfigRequest(random_length=0, version=version))
        if isinstance(dh_config, DhConfigNotModified):
            return self.dh_config
        dh_config.p = int.from_bytes(dh_config.p, 'big', signed=False)
        self.dh_config = dh_config
        return dh_config

    def check_g_a(self, g_a: int, p: int) -> bool:
        if g_a <= 1 or g_a >= p - 1:
            raise ValueError("g_a is invalid (1 < g_a < p - 1 is false).")
        if g_a < 2 ** 1984 or g_a >= p - 2 ** 1984:
            raise ValueError("g_a is invalid (1 < g_a < p - 1 is false).")
        return True

    async def start_secret_chat(self, peer):
        peer = utils.get_input_user(await self.get_input_entity(peer))
        dh_config = await self.get_dh_config()
        a = int.from_bytes(os.urandom(256), 'big', signed=False)
        g_a = pow(dh_config.g, a, dh_config.p)
        self.check_g_a(g_a, dh_config.p)
        res = await self(RequestEncryptionRequest(user_id=peer, g_a=g_a.to_bytes(256, 'big', signed=False)))
        self.temp_secret_chat[res.id] = a
        return res.id

    def generate_secret_in_seq_no(self, chat_id):
        return self.secret_chats[chat_id].in_seq_no * 2 + self.secret_chats[chat_id].in_seq_no_x

    def generate_secret_out_seq_no(self, chat_id):
        return self.secret_chats[chat_id].out_seq_no * 2 + self.secret_chats[chat_id].out_seq_no_x

    async def rekey(self, peer):
        peer = self.get_secret_chat(peer)
        self._log[__name__].debug(f'Rekeying secret chat {peer}')
        dh_config = await self.get_dh_config()
        a = int.from_bytes(os.urandom(256), 'big', signed=False)
        g_a = pow(dh_config.g, a, dh_config.p)
        self.check_g_a(g_a, dh_config.p)
        e = random.randint(10000000, 99999999)
        self.temp_rekeyed_secret_chats[e] = a
        peer.rekeying = [1, e]
        message = DecryptedMessageService(action=DecryptedMessageActionRequestKey(
            g_a=g_a.to_bytes(256, 'big', signed=False),
            exchange_id=e,
        ))
        message = await self.encrypt_secret_message(peer, message)
        await self(SendEncryptedServiceRequest(InputEncryptedChat(peer.id, peer.access_hash), message))

        return e

    async def accept_rekey(self, peer, action: DecryptedMessageActionRequestKey):
        peer = self.get_secret_chat(peer)
        if peer.rekeying[0] != 0:
            my_exchange_id = peer.rekeying[1]
            other_exchange_id = action.exchange_id
            if my_exchange_id > other_exchange_id:
                return
            if my_exchange_id == other_exchange_id:
                peer.rekeying = [0]
                return
        self._log[__name__].debug(f'Accepting rekeying secret chat {peer}')
        dh_config = await self.get_dh_config()
        random_bytes = os.urandom(256)
        b = int.from_bytes(random_bytes, byteorder="big", signed=False)
        g_a = int.from_bytes(action.g_a, 'big', signed=False)
        self.check_g_a(g_a, dh_config.p)
        res = pow(g_a, b, dh_config.p)
        auth_key = res.to_bytes(256, 'big', signed=False)
        key = ChatKey(auth_key)
        key.fingerprint = struct.unpack('<q', sha1(key.auth_key).digest()[-8:])[0]
        self.temp_rekeyed_secret_chats[action.exchange_id] = key
        peer.rekeying = [2, action.exchange_id]
        g_b = pow(dh_config.g, b, dh_config.p)
        self.check_g_a(g_b, dh_config.p)
        message = DecryptedMessageService(action=DecryptedMessageActionAcceptKey(
            g_b=g_b.to_bytes(256, 'big', signed=False),
            exchange_id=action.exchange_id,
            key_fingerprint=key.fingerprint
        ))
        message = await self.encrypt_secret_message(peer, message)
        await self(SendEncryptedServiceRequest(InputEncryptedChat(peer.id, peer.access_hash), message))

    async def commit_rekey(self, peer, action: DecryptedMessageActionAcceptKey):
        peer = self.get_secret_chat(peer)
        if peer.rekeying[0] != 1 or not self.temp_rekeyed_secret_chats.get(action.exchange_id, None):
            peer.rekeying = [0]
            return
        self._log[__name__].debug(f'Committing rekeying secret chat {peer}')
        dh_config = await self.get_dh_config()
        g_b = int.from_bytes(action.g_b, 'big', signed=False)
        self.check_g_a(g_b, dh_config.p)
        res = pow(g_b, self.temp_rekeyed_secret_chats[action.exchange_id], dh_config.p)
        auth_key = res.to_bytes(256, 'big', signed=False)
        key = ChatKey(auth_key)
        key.fingerprint = struct.unpack('<q', sha1(key.auth_key).digest()[-8:])[0]
        if key.fingerprint != action.key_fingerprint:
            message = DecryptedMessageService(action=DecryptedMessageActionAbortKey(
                exchange_id=action.exchange_id,
            ))
            message = await self.encrypt_secret_message(peer, message)
            await self(SendEncryptedServiceRequest(InputEncryptedChat(peer.id, peer.access_hash), message))
            raise SecurityError("Invalid Key fingerprint")
        message = DecryptedMessageService(action=DecryptedMessageActionCommitKey(
            exchange_id=action.exchange_id,
            key_fingerprint=key.fingerprint
        ))
        message = await self.encrypt_secret_message(peer, message)
        await self(SendEncryptedServiceRequest(InputEncryptedChat(peer.id, peer.access_hash), message))
        del self.temp_rekeyed_secret_chats[action.exchange_id]
        peer.rekeying = [0]
        peer.key = key
        peer.ttl = 100
        peer.updated = time()

    async def complete_rekey(self, peer, action: DecryptedMessageActionCommitKey):
        peer = self.get_secret_chat(peer)
        if peer.rekeying[0] != 2 or self.temp_rekeyed_secret_chats.get(action.exchange_id, None):
            return
        if self.temp_rekeyed_secret_chats.get[action.exchange_id] != action.key_fingerprint:
            message = DecryptedMessageService(action=DecryptedMessageActionAbortKey(
                exchange_id=action.exchange_id,
            ))
            message = await self.encrypt_secret_message(peer, message)
            await self(SendEncryptedServiceRequest(InputEncryptedChat(peer.id, peer.access_hash), message))
            raise SecurityError("Invalid Key fingerprint")

        self._log[__name__].debug(f'Completing rekeying secret chat {peer}')
        peer.rekeying = [0]
        peer.key = self.temp_rekeyed_secret_chats[action.exchange_id]
        peer.ttr = 100
        peer.updated = time()
        del self.temp_rekeyed_secret_chats[action.exchange_id]
        message = DecryptedMessageService(action=DecryptedMessageActionNoop())
        message = await self.encrypt_secret_message(peer, message)
        await self(SendEncryptedServiceRequest(InputEncryptedChat(peer.id, peer.access_hash), message))
        self._log[__name__].debug(f'Secret chat {peer} rekeyed succrsfully')

    async def handle_decrypted_message(self, decrypted_message, peer: Chats, file):
        if isinstance(decrypted_message, (DecryptedMessageService, DecryptedMessageService8)):
            if isinstance(decrypted_message.action, DecryptedMessageActionRequestKey):
                await self.accept_rekey(peer, decrypted_message.action)
                return
            elif isinstance(decrypted_message.action, DecryptedMessageActionAcceptKey):
                await self.commit_rekey(peer, decrypted_message.action)
                return
            elif isinstance(decrypted_message.action, DecryptedMessageActionCommitKey):
                await self.commit_rekey(peer, decrypted_message.action)
                return
            elif isinstance(decrypted_message.action, DecryptedMessageActionNotifyLayer):
                peer.layer = decrypted_message.action.layer
                if decrypted_message.action.layer >= 17 and time() - peer.created > 15:
                    await self.notify_layer(peer)
                if decrypted_message.action.layer >= 73:
                    peer.mtproto = 2
                return
            elif isinstance(decrypted_message.action, DecryptedMessageActionSetMessageTTL):
                peer.ttl = decrypted_message.action.ttl_seconds
                return decrypted_message
            elif isinstance(decrypted_message.action, DecryptedMessageActionNoop):
                return
            elif isinstance(decrypted_message.action, DecryptedMessageActionResend):
                decrypted_message.action.start_seq_no -= peer.out_seq_no_x
                decrypted_message.action.end_seq_no -= peer.out_seq_no_x
                decrypted_message.action.start_seq_no //= 2
                decrypted_message.action.end_seq_no //= 2
                self._log[__name__].warning(f"Resending messages for {peer.id}")
                for seq, message in peer.outgoing:
                    if decrypted_message.action.start_seq_no <= seq <= decrypted_message.action.end_seq_no:
                        await self.send_secret_message(peer.id, message.message)
                return
            else:
                return decrypted_message
        elif isinstance(decrypted_message,
                        (DecryptedMessage8, DecryptedMessage23, DecryptedMessage46, DecryptedMessage)):
            decrypted_message.file = file
            return decrypted_message
        elif isinstance(decrypted_message, DecryptedMessageLayer):
            # TODO add checks
            peer.in_seq_no += 1
            if decrypted_message.layer >= 17:
                peer.layer = decrypted_message.layer
            if decrypted_message.layer >= 17 and time() - peer.created > 15:
                await self.notify_layer(peer)
            decrypted_message = decrypted_message.message
            return await self.handle_decrypted_message(decrypted_message, peer, file)

    async def handle_encrypted_update(self, event):
        if not self.secret_chats.get(event.message.chat_id):
            self._log[__name__].debug("Secret chat not saved. skipping")
            return False
        message = event.message

        file = getattr(message, 'file', None)

        auth_key_id = struct.unpack('<q', message.bytes[:8])[0]
        peer = self.get_secret_chat(message.chat_id)
        if not peer.key.fingerprint or \
                auth_key_id != peer.key.fingerprint:
            await self.close_secret_chat(message.chat_id)
            raise ValueError("Key fingerprint mismatch. Chat closed")

        message_key = message.bytes[8:24]
        encrypted_data = message.bytes[24:]
        if peer.mtproto == 2:
            try:
                decrypted_message = self.decrypt_mtproto2(bytes.fromhex(message_key.hex()), message.chat_id,
                                                          bytes.fromhex(encrypted_data.hex()))
            except Exception as e:
                decrypted_message = self.decrypt_mtproto1(bytes.fromhex(message_key.hex()), message.chat_id,
                                                          bytes.fromhex(encrypted_data.hex()))
                peer.mtproto = 1
                self._log[__name__].debug(f"Used MTProto 1 with chat {message.chat_id}")

        else:
            try:
                decrypted_message = self.decrypt_mtproto1(bytes.fromhex(message_key.hex()), message.chat_id,
                                                          bytes.fromhex(encrypted_data.hex()))

            except Exception as e:
                decrypted_message = self.decrypt_mtproto2(bytes.fromhex(message_key.hex()), message.chat_id,
                                                          bytes.fromhex(encrypted_data.hex()))
                peer.mtproto = 2
                self._log[__name__].debug(f"Used MTProto 2 with chat {message.chat_id}")
        peer.ttr -= 1
        if (peer.ttr <= 0 or (time() - peer.updated) > 7 * 24 * 60 * 60) and peer.rekeying[0] == 0:
            await self.rekey(peer)
        peer.incoming[peer.in_seq_no] = message
        return await self.handle_decrypted_message(decrypted_message, peer, file)

    async def encrypt_secret_message(self, peer, message):
        peer = self.get_secret_chat(peer)
        peer.ttr -= 1
        if peer.layer > 8:
            if (peer.ttr <= 0 or (time() - peer.updated) > 7 * 24 * 60 * 60) and peer.rekeying[0] == 0:
                await self.rekey(peer)
            message = DecryptedMessageLayer(layer=peer.layer,
                                            random_bytes=os.urandom(15 + 4 * random.randint(0, 2)),
                                            in_seq_no=self.generate_secret_in_seq_no(peer.id),
                                            out_seq_no=self.generate_secret_out_seq_no(peer.id),
                                            message=message)

            peer.out_seq_no += 1

        peer.outgoing[peer.out_seq_no] = message
        message = bytes(message)
        message = struct.pack('<I', len(message)) + message
        if peer.mtproto == 2:
            padding = (16 - len(message) % 16) % 16
            if padding < 12:
                padding += 16
            message += os.urandom(padding)
            is_admin = (0 if peer.admin else 8)
            first_str = peer.key.auth_key[88 + is_admin:88 + 32 + is_admin]
            message_key = sha256(first_str + message).digest()[8:24]
            aes_key, aes_iv = MTProtoState._calc_key(peer.key.auth_key, message_key,
                                                     peer.admin)
        else:
            message_key = sha1(message).digest()[-16:]
            aes_key, aes_iv = MTProtoState._old_calc_key(peer.key.auth_key, message_key,
                                                         True)
            padding = (16 - len(message) % 16) % 16
            message += os.urandom(padding)
        message = struct.pack('<q', peer.key.fingerprint) + message_key + AES.encrypt_ige(bytes.fromhex(message.hex()),
                                                                                          aes_key,
                                                                                          aes_iv)
        return message

    async def download_secret_media(self, message):
        if not message.file or not isinstance(message.file, EncryptedFile):
            return b""
        key_fingerprint = message.file.key_fingerprint
        key = message.media.key
        iv = message.media.iv
        digest = md5(key + iv).digest()

        fingerprint = int.from_bytes(digest[:4], byteorder="little", signed=True) ^ int.from_bytes(digest[4:8],
                                                                                                   byteorder="little",
                                                                                                   signed=True)
        if fingerprint != key_fingerprint:
            raise SecurityError("Wrong fingerprint")
        media = await self.download_file(InputEncryptedFileLocation(message.file.id, message.file.access_hash),
                                         file=bytes)
        decrypted_data = AES.decrypt_ige(media, message.media.key, message.media.iv)
        return decrypted_data

    async def send_secret_message(self, peer_id, message, ttl=0, reply_to_id=None):
        peer = self.get_secret_chat(peer_id)
        if peer.layer == 8:
            message = DecryptedMessage8(os.urandom(8), message, DecryptedMessageMediaEmpty())
        elif peer.layer == 46:
            message = DecryptedMessage46(ttl, message, reply_to_random_id=reply_to_id)
        else:
            message = DecryptedMessage(ttl, message, reply_to_random_id=reply_to_id)
        data = await self.encrypt_secret_message(peer_id, message)
        res = await self(
            SendEncryptedRequest(peer=peer.input_chat, data=data))
        return res

    async def upload_secret_file(self, file):
        key = os.urandom(32)
        iv = os.urandom(32)
        digest = md5(key + iv).digest()
        fingerprint = int.from_bytes(digest[:4], byteorder="little", signed=True) ^ int.from_bytes(digest[4:8],
                                                                                                   byteorder="little",
                                                                                                   signed=True)

        file = await self.upload_file(file, key=key, iv=iv)
        if isinstance(file, InputFileBig):
            file = InputEncryptedFileBigUploaded(file.id, file.parts, fingerprint)
        elif isinstance(file, InputFile):
            file = InputEncryptedFileUploaded(file.id, file.parts, "", fingerprint)

        return file, fingerprint, key, iv

    async def send_secret_document(self, peer, document, thumb: bytes, thumb_w: int, thumb_h: int, file_name: str,
                                   mime_type: str, size: int, attributes=None, ttl=0, caption=""):
        if attributes is None:
            attributes = []
        peer = self.get_secret_chat(peer)
        file, fingerprint, key, iv = await self.upload_secret_file(document)
        if peer.layer == 8:
            message = DecryptedMessage8(os.urandom(8), caption,
                                        DecryptedMessageMediaDocument23(thumb, thumb_w, thumb_h, file_name, mime_type,
                                                                        size, key, iv))
        elif peer.layer == 46:
            message = DecryptedMessage46(ttl, caption,
                                         media=DecryptedMessageMediaDocument(thumb, thumb_w, thumb_h, mime_type,
                                                                             size, key, iv, attributes, caption))
        else:
            message = DecryptedMessage(ttl, caption,
                                       media=DecryptedMessageMediaDocument(thumb, thumb_w, thumb_h, mime_type,
                                                                           size, key, iv, attributes, caption))
        data = await self.encrypt_secret_message(peer, message)
        res = await self(SendEncryptedFileRequest(peer.input_chat, data, file=file))
        return res

    async def send_secret_audio(self, peer, audio, duration, mime_type, size, ttl=0, caption=""):
        peer = self.get_secret_chat(peer)
        file, fingerprint, key, iv = await self.upload_secret_file(audio)
        if peer.layer == 8:
            message = DecryptedMessage8(os.urandom(8), caption,
                                        DecryptedMessageMediaAudio8(duration, size, key, iv))
        elif peer.layer == 46:
            message = DecryptedMessage46(ttl, caption,
                                         media=DecryptedMessageMediaAudio(duration, mime_type, size, key, iv))
        else:
            message = DecryptedMessage(ttl, caption,
                                       media=DecryptedMessageMediaAudio(duration, mime_type, size, key, iv))
        data = await self.encrypt_secret_message(peer, message)
        res = await self(SendEncryptedFileRequest(peer.input_chat, data, file=file))
        return res

    async def send_secret_video(self, peer, video, thumb: bytes, thumb_w: int, thumb_h: int, duration: int,
                                mime_type: str, w: int,
                                h: int, size, ttl=0, caption=""):
        peer = self.get_secret_chat(peer)
        file, fingerprint, key, iv = await self.upload_secret_file(video)

        if peer.layer == 8:
            message = DecryptedMessage8(os.urandom(8), caption,
                                        DecryptedMessageMediaVideo8(thumb, thumb_w, thumb_h, duration, w, h, size, key,
                                                                    iv))
        elif peer.layer == 46:
            message = DecryptedMessage46(ttl, caption,
                                         media=DecryptedMessageMediaVideo(thumb, thumb_w, thumb_h, duration, mime_type,
                                                                          w, h, size, key, iv,
                                                                          caption))
        else:
            message = DecryptedMessage(ttl, caption,
                                       media=DecryptedMessageMediaVideo(thumb, thumb_w, thumb_h, duration, mime_type,
                                                                        w, h, size, key, iv,
                                                                        caption))
        data = await self.encrypt_secret_message(peer, message)
        res = await self(SendEncryptedFileRequest(peer.input_chat, data, file=file))
        return res

    async def send_secret_photo(self, peer, image, thumb, thumb_w, thumb_h, w, h, size, caption="",
                                ttl=0):
        peer = self.get_secret_chat(peer)

        file, fingerprint, key, iv = await self.upload_secret_file(image)
        if peer.layer == 8:
            message = DecryptedMessage8(os.urandom(8), caption,
                                        DecryptedMessageMediaPhoto23(thumb, thumb_w, thumb_h, w, h, size, key, iv))
        elif peer.layer == 46:
            message = DecryptedMessage46(ttl, caption,
                                         media=DecryptedMessageMediaPhoto(thumb, thumb_w, thumb_h, w, h, size, key, iv,
                                                                          caption))
        else:
            message = DecryptedMessage(ttl, caption,
                                       media=DecryptedMessageMediaPhoto(thumb, thumb_w, thumb_h, w, h, size, key, iv,
                                                                        caption))
        data = await self.encrypt_secret_message(peer, message)
        res = await self(SendEncryptedFileRequest(peer.input_chat, data, file=file))
        return res

    async def notify_layer(self, peer):
        if isinstance(peer, int):
            peer = self.secret_chats[peer]
        else:
            peer = self.secret_chats[peer.id]
        if peer.layer == 8:
            return
        message = DecryptedMessageService8(action=DecryptedMessageActionNotifyLayer(
            layer=min(DEFAULT_LAYER, peer.layer)), random_bytes=os.urandom(15 + 4 * random.randint(0, 2)))
        data = await self.encrypt_secret_message(peer.id, message)
        return await self(
            SendEncryptedServiceRequest(peer=InputEncryptedChat(peer.id, peer.access_hash),
                                        data=data))

    async def close_secret_chat(self, peer):

        if self.secret_chats.get(peer.id, None):
            del self.secret_chats[peer]
        if self.temp_secret_chat.get(peer.id, None):
            del self.temp_secret_chat[peer.id]
        try:
            await self(DiscardEncryptionRequest(peer.id))
        except EncryptionAlreadyDeclinedError:
            pass

    def decrypt_mtproto2(self, message_key, chat_id, encrypted_data):
        peer = self.get_secret_chat(chat_id)

        aes_key, aes_iv = MTProtoState._calc_key(self.secret_chats[chat_id].key.auth_key,
                                                 message_key,
                                                 not self.secret_chats[chat_id].admin)

        decrypted_data = AES.decrypt_ige(encrypted_data, aes_key, aes_iv)
        message_data_length = struct.unpack('<I', decrypted_data[:4])[0]
        message_data = decrypted_data[4:message_data_length + 4]
        if message_data_length > len(decrypted_data):
            raise SecurityError("message data length is too big")
        is_admin = peer.admin
        first_str = peer.key.auth_key[88 + is_admin:88 + 32 + is_admin]

        if message_key != sha256(first_str + decrypted_data).digest()[8:24]:
            raise SecurityError("Message key mismatch")
        if len(decrypted_data) - 4 - message_data_length < 12:
            raise SecurityError("Padding is too small")
        if len(decrypted_data) % 16 != 0:
            raise SecurityError("Decrpyted data not divisble by 16")

        return BinaryReader(message_data).tgread_object()

    def decrypt_mtproto1(self, message_key, chat_id, encrypted_data):
        aes_key, aes_iv = MTProtoState._old_calc_key(self.secret_chats[chat_id].key.auth_key,
                                                     message_key,
                                                     True)
        decrypted_data = AES.decrypt_ige(encrypted_data, aes_key, aes_iv)
        message_data_length = struct.unpack('<I', decrypted_data[:4])[0]
        message_data = decrypted_data[4:message_data_length + 4]
        if message_data_length > len(decrypted_data):
            raise SecurityError("message data length is too big")

        if message_key != sha1(decrypted_data[:4 + message_data_length]).digest()[-16:]:
            raise SecurityError("Message key mismatch")
        if len(decrypted_data) - 4 - message_data_length > 15:
            raise SecurityError("Difference is too big")
        if len(decrypted_data) % 16 != 0:
            raise SecurityError("Decrypted data can not be divided by 16")

        return BinaryReader(message_data).tgread_object()

    async def accept_secret_chat(self, chat: TypeEncryptedChat):
        if chat.id == 0:
            raise ValueError("Already accepted")
        dh_config = await self.get_dh_config()
        random_bytes = os.urandom(256)
        b = int.from_bytes(random_bytes, byteorder="big", signed=False)
        g_a = int.from_bytes(chat.g_a, 'big', signed=False)
        self.check_g_a(g_a, dh_config.p)
        res = pow(g_a, b, dh_config.p)
        auth_key = res.to_bytes(256, 'big', signed=False)
        key = ChatKey(auth_key)
        key.fingerprint = struct.unpack('<q', sha1(key.auth_key).digest()[-8:])[0]
        input_peer = InputEncryptedChat(chat_id=chat.id, access_hash=chat.access_hash)
        secret_chat = Chats(chat.id, chat.access_hash, key, admin=False, user_id=chat.admin_id, input_chat=input_peer)
        self.secret_chats[chat.id] = secret_chat
        g_b = pow(dh_config.g, b, dh_config.p)
        self.check_g_a(g_b, dh_config.p)
        result = await self(
            AcceptEncryptionRequest(input_peer, g_b=g_b.to_bytes(256, 'big', signed=False),
                                    key_fingerprint=key.fingerprint))
        await self.notify_layer(chat)
        return result

    async def finish_secret_chat_creation(self, chat):
        dh_config = await self.get_dh_config()
        g_a_or_b = int.from_bytes(chat.g_a_or_b, "big", signed=False)
        self.check_g_a(g_a_or_b, dh_config.p)
        auth_key = pow(g_a_or_b, self.temp_secret_chat[chat.id], dh_config.p).to_bytes(256, "big", signed=False)
        del self.temp_secret_chat[chat.id]
        key = ChatKey(auth_key)
        key.fingerprint = struct.unpack('<q', sha1(key.auth_key).digest()[-8:])[0]
        if key.fingerprint != chat.key_fingerprint:
            raise ValueError("Wrong fingerprint")
        key.visualization_orig = sha1(key.auth_key).digest()[16:]
        key.visualization_46 = sha256(key.auth_key).digest()[20:]
        input_peer = InputEncryptedChat(chat_id=chat.id, access_hash=chat.access_hash)
        self.secret_chats[chat.id] = Chats(
            chat.id,
            chat.access_hash,
            key,
            True,
            chat.participant_id,
            input_peer
        )
        await self.notify_layer(chat)
