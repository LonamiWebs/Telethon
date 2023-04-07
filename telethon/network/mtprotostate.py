import os
import struct
import time
from hashlib import sha256
from collections import deque

from ..crypto import AES
from ..errors import SecurityError, InvalidBufferError
from ..extensions import BinaryReader
from ..tl.core import TLMessage
from ..tl.tlobject import TLRequest
from ..tl.functions import InvokeAfterMsgRequest
from ..tl.core.gzippacked import GzipPacked
from ..tl.types import BadServerSalt, BadMsgNotification


# N is not  specified in https://core.telegram.org/mtproto/security_guidelines#checking-msg-id, but 500 is reasonable
MAX_RECENT_MSG_IDS = 500

MSG_TOO_NEW_DELTA = 30
MSG_TOO_OLD_DELTA = 300

# Something must be wrong if we ignore too many messages at the same time
MAX_CONSECUTIVE_IGNORED = 10


class _OpaqueRequest(TLRequest):
    """
    Wraps a serialized request into a type that can be serialized again.
    """
    def __init__(self, data: bytes):
        self.data = data

    def _bytes(self):
        return self.data



class MTProtoState:
    """
    `telethon.network.mtprotosender.MTProtoSender` needs to hold a state
    in order to be able to encrypt and decrypt incoming/outgoing messages,
    as well as generating the message IDs. Instances of this class hold
    together all the required information.

    It doesn't make sense to use `telethon.sessions.abstract.Session` for
    the sender because the sender should *not* be concerned about storing
    this information to disk, as one may create as many senders as they
    desire to any other data center, or some CDN. Using the same session
    for all these is not a good idea as each need their own authkey, and
    the concept of "copying" sessions with the unnecessary entities or
    updates state for these connections doesn't make sense.

    While it would be possible to have a `MTProtoPlainState` that does no
    encryption so that it was usable through the `MTProtoLayer` and thus
    avoid the need for a `MTProtoPlainSender`, the `MTProtoLayer` is more
    focused to efficiency and this state is also more advanced (since it
    supports gzipping and invoking after other message IDs). There are too
    many methods that would be needed to make it convenient to use for the
    authentication process, at which point the `MTProtoPlainSender` is better.
    """
    def __init__(self, auth_key, loggers):
        self.auth_key = auth_key
        self._log = loggers[__name__]
        self.time_offset = 0
        self.salt = 0

        self.id = self._sequence = self._last_msg_id = None
        self._recent_remote_ids = deque(maxlen=MAX_RECENT_MSG_IDS)
        self._highest_remote_id = 0
        self._ignore_count = 0
        self.reset()

    def reset(self):
        """
        Resets the state.
        """
        # Session IDs can be random on every connection
        self.id = struct.unpack('q', os.urandom(8))[0]
        self._sequence = 0
        self._last_msg_id = 0
        self._recent_remote_ids.clear()
        self._highest_remote_id = 0
        self._ignore_count = 0

    def update_message_id(self, message):
        """
        Updates the message ID to a new one,
        used when the time offset changed.
        """
        message.msg_id = self._get_new_msg_id()

    @staticmethod
    def _calc_key(auth_key, msg_key, client):
        """
        Calculate the key based on Telegram guidelines for MTProto 2,
        specifying whether it's the client or not. See
        https://core.telegram.org/mtproto/description#defining-aes-key-and-initialization-vector
        """
        x = 0 if client else 8
        sha256a = sha256(msg_key + auth_key[x: x + 36]).digest()
        sha256b = sha256(auth_key[x + 40:x + 76] + msg_key).digest()

        aes_key = sha256a[:8] + sha256b[8:24] + sha256a[24:32]
        aes_iv = sha256b[:8] + sha256a[8:24] + sha256b[24:32]

        return aes_key, aes_iv

    def write_data_as_message(self, buffer, data, content_related,
                              *, after_id=None):
        """
        Writes a message containing the given data into buffer.

        Returns the message id.
        """
        msg_id = self._get_new_msg_id()
        seq_no = self._get_seq_no(content_related)
        if after_id is None:
            body = GzipPacked.gzip_if_smaller(content_related, data)
        else:
            # The `RequestState` stores `bytes(request)`, not the request itself.
            # `invokeAfterMsg` wants a `TLRequest` though, hence the wrapping.
            body = GzipPacked.gzip_if_smaller(content_related,
                bytes(InvokeAfterMsgRequest(after_id, _OpaqueRequest(data))))

        buffer.write(struct.pack('<qii', msg_id, seq_no, len(body)))
        buffer.write(body)
        return msg_id

    def encrypt_message_data(self, data):
        """
        Encrypts the given message data using the current authorization key
        following MTProto 2.0 guidelines core.telegram.org/mtproto/description.
        """
        data = struct.pack('<qq', self.salt, self.id) + data
        padding = os.urandom(-(len(data) + 12) % 16 + 12)

        # Being substr(what, offset, length); x = 0 for client
        # "msg_key_large = SHA256(substr(auth_key, 88+x, 32) + pt + padding)"
        msg_key_large = sha256(
            self.auth_key.key[88:88 + 32] + data + padding).digest()

        # "msg_key = substr (msg_key_large, 8, 16)"
        msg_key = msg_key_large[8:24]
        aes_key, aes_iv = self._calc_key(self.auth_key.key, msg_key, True)

        key_id = struct.pack('<Q', self.auth_key.key_id)
        return (key_id + msg_key +
                AES.encrypt_ige(data + padding, aes_key, aes_iv))

    def decrypt_message_data(self, body):
        """
        Inverse of `encrypt_message_data` for incoming server messages.
        """
        now = time.time() + self.time_offset  # get the time as early as possible, even if other checks make it go unused

        if len(body) < 8:
            raise InvalidBufferError(body)

        # TODO Check salt, session_id and sequence_number
        key_id = struct.unpack('<Q', body[:8])[0]
        if key_id != self.auth_key.key_id:
            raise SecurityError('Server replied with an invalid auth key')

        msg_key = body[8:24]
        aes_key, aes_iv = self._calc_key(self.auth_key.key, msg_key, False)
        body = AES.decrypt_ige(body[24:], aes_key, aes_iv)

        # https://core.telegram.org/mtproto/security_guidelines
        # Sections "checking sha256 hash" and "message length"
        our_key = sha256(self.auth_key.key[96:96 + 32] + body)
        if msg_key != our_key.digest()[8:24]:
            raise SecurityError(
                "Received msg_key doesn't match with expected one")

        reader = BinaryReader(body)
        reader.read_long()  # remote_salt
        if reader.read_long() != self.id:
            raise SecurityError('Server replied with a wrong session ID (see FAQ for details)')

        remote_msg_id = reader.read_long()

        if remote_msg_id % 2 != 1:
            raise SecurityError('Server sent an even msg_id')

        # Only perform the (somewhat expensive) check of duplicate if we did receive a lower ID
        if remote_msg_id <= self._highest_remote_id and remote_msg_id in self._recent_remote_ids:
            self._log.warning('Server resent the older message %d, ignoring', remote_msg_id)
            self._count_ignored()
            return None

        remote_sequence = reader.read_int()
        reader.read_int()  # msg_len for the inner object, padding ignored

        # We could read msg_len bytes and use those in a new reader to read
        # the next TLObject without including the padding, but since the
        # reader isn't used for anything else after this, it's unnecessary.
        obj = reader.tgread_object()

        # "Certain client-to-server service messages containing data sent by the client to the
        # server (for example, msg_id of a recent client query) may, nonetheless, be processed
        # on the client even if the time appears to be "incorrect". This is especially true of
        # messages to change server_salt and notifications about invalid time on the client."
        #
        # This means we skip the time check for certain types of messages.
        if obj.CONSTRUCTOR_ID not in (BadServerSalt.CONSTRUCTOR_ID, BadMsgNotification.CONSTRUCTOR_ID):
            remote_msg_time = remote_msg_id >> 32
            time_delta = now - remote_msg_time

            if time_delta > MSG_TOO_OLD_DELTA:
                self._log.warning('Server sent a very old message with ID %d, ignoring (see FAQ for details)', remote_msg_id)
                self._count_ignored()
                return None

            if -time_delta > MSG_TOO_NEW_DELTA:
                self._log.warning('Server sent a very new message with ID %d, ignoring (see FAQ for details)', remote_msg_id)
                self._count_ignored()
                return None

        self._recent_remote_ids.append(remote_msg_id)
        self._highest_remote_id = remote_msg_id
        self._ignore_count = 0

        return TLMessage(remote_msg_id, remote_sequence, obj)

    def _count_ignored(self):
        # It's possible that ignoring a message "bricks" the connection,
        # but this should not happen unless there's something else wrong.
        self._ignore_count += 1
        if self._ignore_count >= MAX_CONSECUTIVE_IGNORED:
            raise SecurityError('Too many messages had to be ignored consecutively')

    def _get_new_msg_id(self):
        """
        Generates a new unique message ID based on the current
        time (in ms) since epoch, applying a known time offset.
        """
        now = time.time() + self.time_offset
        nanoseconds = int((now - int(now)) * 1e+9)
        new_msg_id = (int(now) << 32) | (nanoseconds << 2)

        if self._last_msg_id >= new_msg_id:
            new_msg_id = self._last_msg_id + 4

        self._last_msg_id = new_msg_id
        return new_msg_id

    def update_time_offset(self, correct_msg_id):
        """
        Updates the time offset to the correct
        one given a known valid message ID.
        """
        bad = self._get_new_msg_id()
        old = self.time_offset

        now = int(time.time())
        correct = correct_msg_id >> 32
        self.time_offset = correct - now

        if self.time_offset != old:
            self._last_msg_id = 0
            self._log.debug(
                'Updated time offset (old offset %d, bad %d, good %d, new %d)',
                old, bad, correct_msg_id, self.time_offset
            )

        return self.time_offset

    def _get_seq_no(self, content_related):
        """
        Generates the next sequence number depending on whether
        it should be for a content-related query or not.
        """
        if content_related:
            result = self._sequence * 2 + 1
            self._sequence += 1
            return result
        else:
            return self._sequence * 2
