import gzip
import logging
import struct

from .. import helpers as utils
from ..crypto import AES
from ..errors import (
    BadMessageError, InvalidChecksumError, BrokenAuthKeyError,
    rpc_message_to_error
)
from ..extensions import BinaryReader
from ..tl import TLMessage, MessageContainer, GzipPacked
from ..tl.all_tlobjects import tlobjects
from ..tl.types import (
    MsgsAck, Pong, BadServerSalt, BadMsgNotification,
    MsgNewDetailedInfo, NewSessionCreated, MsgDetailedInfo
)
from ..tl.functions.auth import LogOutRequest

logging.getLogger(__name__).addHandler(logging.NullHandler())


class MtProtoSender:
    """MTProto Mobile Protocol sender
       (https://core.telegram.org/mtproto/description).

       Note that this class is not thread-safe, and calling send/receive
       from two or more threads at the same time is undefined behaviour.
       Rationale: a new connection should be spawned to send/receive requests
                  in parallel, so thread-safety (hence locking) isn't needed.
    """

    def __init__(self, session, connection):
        """Creates a new MtProtoSender configured to send messages through
           'connection' and using the parameters from 'session'.
        """
        self.session = session
        self.connection = connection
        self._logger = logging.getLogger(__name__)

        # Message IDs that need confirmation
        self._need_confirmation = set()

        # Requests (as msg_id: Message) sent waiting to be received
        self._pending_receive = {}

    def connect(self):
        """Connects to the server"""
        self.connection.connect(self.session.server_address, self.session.port)

    def is_connected(self):
        return self.connection.is_connected()

    def disconnect(self):
        """Disconnects from the server"""
        self.connection.close()
        self._need_confirmation.clear()
        self._clear_all_pending()

    def clone(self):
        """Creates a copy of this MtProtoSender as a new connection"""
        return MtProtoSender(self.session, self.connection.clone())

    # region Send and receive

    def send(self, *requests):
        """Sends the specified MTProtoRequest, previously sending any message
           which needed confirmation."""

        # Finally send our packed request(s)
        messages = [TLMessage(self.session, r) for r in requests]
        self._pending_receive.update({m.msg_id: m for m in messages})

        # Pack everything in the same container if we need to send AckRequests
        if self._need_confirmation:
            messages.append(
                TLMessage(self.session, MsgsAck(list(self._need_confirmation)))
            )
            self._need_confirmation.clear()

        if len(messages) == 1:
            message = messages[0]
        else:
            message = TLMessage(self.session, MessageContainer(messages))
            # On bad_msg_salt errors, Telegram will reply with the ID of
            # the container and not the requests it contains, so in case
            # this happens we need to know to which container they belong.
            for m in messages:
                m.container_msg_id = message.msg_id

        self._send_message(message)

    def _send_acknowledge(self, msg_id):
        """Sends a message acknowledge for the given msg_id"""
        self._send_message(TLMessage(self.session, MsgsAck([msg_id])))

    def receive(self, update_state):
        """Receives a single message from the connected endpoint.

           This method returns nothing, and will only affect other parts
           of the MtProtoSender such as the updates callback being fired
           or a pending request being confirmed.

           Any unhandled object (likely updates) will be passed to
           update_state.process(TLObject).
        """
        try:
            body = self.connection.recv()
        except (BufferError, InvalidChecksumError):
            # TODO BufferError, we should spot the cause...
            # "No more bytes left"; something wrong happened, clear
            # everything to be on the safe side, or:
            #
            # "This packet should be skipped"; since this may have
            # been a result for a request, invalidate every request
            # and just re-invoke them to avoid problems
            self._clear_all_pending()
            return

        message, remote_msg_id, remote_seq = self._decode_msg(body)
        with BinaryReader(message) as reader:
            self._process_msg(remote_msg_id, remote_seq, reader, update_state)

    # endregion

    # region Low level processing

    def _send_message(self, message):
        """Sends the given Message(TLObject) encrypted through the network"""

        plain_text = \
            struct.pack('<QQ', self.session.salt, self.session.id) \
            + bytes(message)

        msg_key = utils.calc_msg_key(plain_text)
        key_id = struct.pack('<Q', self.session.auth_key.key_id)
        key, iv = utils.calc_key(self.session.auth_key.key, msg_key, True)
        cipher_text = AES.encrypt_ige(plain_text, key, iv)

        result = key_id + msg_key + cipher_text
        self.connection.send(result)

    def _decode_msg(self, body):
        """Decodes an received encrypted message body bytes"""
        message = None
        remote_msg_id = None
        remote_sequence = None

        with BinaryReader(body) as reader:
            if len(body) < 8:
                if body == b'l\xfe\xff\xff':
                    raise BrokenAuthKeyError()
                else:
                    raise BufferError("Can't decode packet ({})".format(body))

            # TODO Check for both auth key ID and msg_key correctness
            reader.read_long()  # remote_auth_key_id
            msg_key = reader.read(16)

            key, iv = utils.calc_key(self.session.auth_key.key, msg_key, False)
            plain_text = AES.decrypt_ige(
                reader.read(len(body) - reader.tell_position()), key, iv)

            with BinaryReader(plain_text) as plain_text_reader:
                plain_text_reader.read_long()  # remote_salt
                plain_text_reader.read_long()  # remote_session_id
                remote_msg_id = plain_text_reader.read_long()
                remote_sequence = plain_text_reader.read_int()
                msg_len = plain_text_reader.read_int()
                message = plain_text_reader.read(msg_len)

        return message, remote_msg_id, remote_sequence

    def _process_msg(self, msg_id, sequence, reader, state):
        """Processes and handles a Telegram message.

           Returns True if the message was handled correctly and doesn't
           need to be skipped. Returns False otherwise.
        """

        # TODO Check salt, session_id and sequence_number
        self._need_confirmation.add(msg_id)

        code = reader.read_int(signed=False)
        reader.seek(-4)

        # The following codes are "parsed manually"
        if code == 0xf35c6d01:  # rpc_result, (response of an RPC call)
            return self._handle_rpc_result(msg_id, sequence, reader)

        if code == Pong.CONSTRUCTOR_ID:
            return self._handle_pong(msg_id, sequence, reader)

        if code == MessageContainer.CONSTRUCTOR_ID:
            return self._handle_container(msg_id, sequence, reader, state)

        if code == GzipPacked.CONSTRUCTOR_ID:
            return self._handle_gzip_packed(msg_id, sequence, reader, state)

        if code == BadServerSalt.CONSTRUCTOR_ID:
            return self._handle_bad_server_salt(msg_id, sequence, reader)

        if code == BadMsgNotification.CONSTRUCTOR_ID:
            return self._handle_bad_msg_notification(msg_id, sequence, reader)

        if code == MsgDetailedInfo.CONSTRUCTOR_ID:
            return self._handle_msg_detailed_info(msg_id, sequence, reader)

        if code == MsgNewDetailedInfo.CONSTRUCTOR_ID:
            return self._handle_msg_new_detailed_info(msg_id, sequence, reader)

        if code == NewSessionCreated.CONSTRUCTOR_ID:
            return self._handle_new_session_created(msg_id, sequence, reader)

        if code == MsgsAck.CONSTRUCTOR_ID:  # may handle the request we wanted
            ack = reader.tgread_object()
            assert isinstance(ack, MsgsAck)
            # Ignore every ack request *unless* when logging out, when it's
            # when it seems to only make sense. We also need to set a non-None
            # result since Telegram doesn't send the response for these.
            for msg_id in ack.msg_ids:
                r = self._pop_request_of_type(msg_id, LogOutRequest)
                if r:
                    r.result = True  # Telegram won't send this value
                    r.confirm_received.set()
                    self._logger.debug('Message ack confirmed', r)

            return True

        # If the code is not parsed manually then it should be a TLObject.
        if code in tlobjects:
            result = reader.tgread_object()
            self.session.process_entities(result)
            if state:
                state.process(result)

            return True

        self._logger.debug(
            '[WARN] Unknown message: {}, data left in the buffer: {}'
            .format(
                hex(code), repr(reader.get_bytes()[reader.tell_position():])
            )
        )
        return False

    # endregion

    # region Message handling

    def _pop_request(self, msg_id):
        """Pops a pending REQUEST from self._pending_receive, or
           returns None if it's not found.
        """
        message = self._pending_receive.pop(msg_id, None)
        if message:
            return message.request

    def _pop_request_of_type(self, msg_id, t):
        """Pops a pending REQUEST from self._pending_receive if it matches
           the given type, or returns None if it's not found/doesn't match.
        """
        message = self._pending_receive.get(msg_id, None)
        if message and isinstance(message.request, t):
            return self._pending_receive.pop(msg_id).request

    def _pop_requests_of_container(self, container_msg_id):
        """Pops the pending requests (plural) from self._pending_receive if
           they were sent on a container that matches container_msg_id.
        """
        msgs = [msg for msg in self._pending_receive.values()
                if msg.container_msg_id == container_msg_id]

        requests = [msg.request for msg in msgs]
        for msg in msgs:
            self._pending_receive.pop(msg.msg_id, None)
        return requests

    def _clear_all_pending(self):
        for r in self._pending_receive.values():
            r.request.confirm_received.set()
        self._pending_receive.clear()

    def _resend_request(self, msg_id):
        """Re-sends the request that belongs to a certain msg_id. This may
           also be the msg_id of a container if they were sent in one.
        """
        request = self._pop_request(msg_id)
        if request:
            return self.send(request)
        requests = self._pop_requests_of_container(msg_id)
        if requests:
            return self.send(*requests)

    def _handle_pong(self, msg_id, sequence, reader):
        self._logger.debug('Handling pong')
        pong = reader.tgread_object()
        assert isinstance(pong, Pong)

        request = self._pop_request(pong.msg_id)
        if request:
            self._logger.debug('Pong confirmed a request')
            request.result = pong
            request.confirm_received.set()

        return True

    def _handle_container(self, msg_id, sequence, reader, state):
        self._logger.debug('Handling container')
        for inner_msg_id, _, inner_len in MessageContainer.iter_read(reader):
            begin_position = reader.tell_position()

            # Note that this code is IMPORTANT for skipping RPC results of
            # lost requests (i.e., ones from the previous connection session)
            try:
                if not self._process_msg(inner_msg_id, sequence, reader, state):
                    reader.set_position(begin_position + inner_len)
            except:
                # If any error is raised, something went wrong; skip the packet
                reader.set_position(begin_position + inner_len)
                raise

        return True

    def _handle_bad_server_salt(self, msg_id, sequence, reader):
        self._logger.debug('Handling bad server salt')
        bad_salt = reader.tgread_object()
        assert isinstance(bad_salt, BadServerSalt)

        # Our salt is unsigned, but the objects work with signed salts
        self.session.salt = struct.unpack(
            '<Q', struct.pack('<q', bad_salt.new_server_salt)
        )[0]
        self.session.save()

        # "the bad_server_salt response is received with the
        # correct salt, and the message is to be re-sent with it"
        self._resend_request(bad_salt.bad_msg_id)
        return True

    def _handle_bad_msg_notification(self, msg_id, sequence, reader):
        self._logger.debug('Handling bad message notification')
        bad_msg = reader.tgread_object()
        assert isinstance(bad_msg, BadMsgNotification)

        error = BadMessageError(bad_msg.error_code)
        if bad_msg.error_code in (16, 17):
            # sent msg_id too low or too high (respectively).
            # Use the current msg_id to determine the right time offset.
            self.session.update_time_offset(correct_msg_id=msg_id)
            self._logger.debug('Read Bad Message error: ' + str(error))
            self._logger.debug('Attempting to use the correct time offset.')
            self._resend_request(bad_msg.bad_msg_id)
            return True
        elif bad_msg.error_code == 32:
            # msg_seqno too low, so just pump it up by some "large" amount
            # TODO A better fix would be to start with a new fresh session ID
            self.session._sequence += 64
            self._resend_request(bad_msg.bad_msg_id)
            return True
        elif bad_msg.error_code == 33:
            # msg_seqno too high never seems to happen but just in case
            self.session._sequence -= 16
            self._resend_request(bad_msg.bad_msg_id)
            return True
        else:
            raise error

    def _handle_msg_detailed_info(self, msg_id, sequence, reader):
        msg_new = reader.tgread_object()
        assert isinstance(msg_new, MsgDetailedInfo)

        # TODO For now, simply ack msg_new.answer_msg_id
        # Relevant tdesktop source code: https://goo.gl/VvpCC6
        self._send_acknowledge(msg_new.answer_msg_id)
        return True

    def _handle_msg_new_detailed_info(self, msg_id, sequence, reader):
        msg_new = reader.tgread_object()
        assert isinstance(msg_new, MsgNewDetailedInfo)

        # TODO For now, simply ack msg_new.answer_msg_id
        # Relevant tdesktop source code: https://goo.gl/G7DPsR
        self._send_acknowledge(msg_new.answer_msg_id)
        return True

    def _handle_new_session_created(self, msg_id, sequence, reader):
        new_session = reader.tgread_object()
        assert isinstance(new_session, NewSessionCreated)
        # TODO https://goo.gl/LMyN7A
        return True

    def _handle_rpc_result(self, msg_id, sequence, reader):
        self._logger.debug('Handling RPC result')
        reader.read_int(signed=False)  # code
        request_id = reader.read_long()
        inner_code = reader.read_int(signed=False)

        request = self._pop_request(request_id)

        if inner_code == 0x2144ca19:  # RPC Error
            if self.session.report_errors and request:
                error = rpc_message_to_error(
                    reader.read_int(), reader.tgread_string(),
                    report_method=type(request).CONSTRUCTOR_ID
                )
            else:
                error = rpc_message_to_error(
                    reader.read_int(), reader.tgread_string()
                )

            # Acknowledge that we received the error
            self._send_acknowledge(request_id)

            if request:
                request.rpc_error = error
                request.confirm_received.set()
            # else TODO Where should this error be reported?
            # Read may be async. Can an error not-belong to a request?
            self._logger.debug('Read RPC error: %s', str(error))
            return True  # All contents were read okay

        elif request:
            self._logger.debug('Reading request response')
            if inner_code == 0x3072cfa1:  # GZip packed
                unpacked_data = gzip.decompress(reader.tgread_bytes())
                with BinaryReader(unpacked_data) as compressed_reader:
                    request.on_response(compressed_reader)
            else:
                reader.seek(-4)
                request.on_response(reader)

            self.session.process_entities(request.result)
            request.confirm_received.set()
            return True

        # If it's really a result for RPC from previous connection
        # session, it will be skipped by the handle_container()
        self._logger.debug('Lost request will be skipped.')
        return False

    def _handle_gzip_packed(self, msg_id, sequence, reader, state):
        self._logger.debug('Handling gzip packed data')
        with BinaryReader(GzipPacked.read(reader)) as compressed_reader:
            # We are reentering process_msg, which seemingly the same msg_id
            # to the self._need_confirmation set. Remove it from there first
            # to avoid any future conflicts (i.e. if we "ignore" messages
            # that we are already aware of, see 1a91c02 and old 63dfb1e)
            self._need_confirmation -= {msg_id}
            return self._process_msg(msg_id, sequence, compressed_reader, state)

    # endregion
