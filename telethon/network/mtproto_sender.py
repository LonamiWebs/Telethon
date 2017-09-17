import gzip
import logging
from threading import RLock

from .. import helpers as utils
from ..crypto import AES
from ..errors import BadMessageError, InvalidChecksumError, rpc_message_to_error
from ..extensions import BinaryReader, BinaryWriter
from ..tl.all_tlobjects import tlobjects
from ..tl.types import MsgsAck

logging.getLogger(__name__).addHandler(logging.NullHandler())


class MtProtoSender:
    """MTProto Mobile Protocol sender
       (https://core.telegram.org/mtproto/description)
    """

    def __init__(self, connection, session):
        """Creates a new MtProtoSender configured to send messages through
           'connection' and using the parameters from 'session'.
        """
        self.connection = connection
        self.session = session
        self._logger = logging.getLogger(__name__)

        self._need_confirmation = []  # Message IDs that need confirmation
        self._pending_receive = []  # Requests sent waiting to be received

        # Sending and receiving are independent, but two threads cannot
        # send or receive at the same time no matter what.
        self._send_lock = RLock()
        self._recv_lock = RLock()

        # Used when logging out, the only request that seems to use 'ack'
        # TODO There might be a better way to handle msgs_ack requests
        self.logging_out = False

    def connect(self):
        """Connects to the server"""
        self.connection.connect()

    def is_connected(self):
        return self.connection.is_connected()

    def disconnect(self):
        """Disconnects from the server"""
        self.connection.close()

    # region Send and receive

    def send(self, request):
        """Sends the specified MTProtoRequest, previously sending any message
           which needed confirmation."""

        # If any message needs confirmation send an AckRequest first
        self._send_acknowledges()

        # Finally send our packed request
        with BinaryWriter() as writer:
            request.on_send(writer)
            self._send_packet(writer.get_bytes(), request)
            self._pending_receive.append(request)

        # And update the saved session
        self.session.save()

    def _send_acknowledges(self):
        """Sends a messages acknowledge for all those who _need_confirmation"""
        if self._need_confirmation:
            msgs_ack = MsgsAck(self._need_confirmation)
            with BinaryWriter() as writer:
                msgs_ack.on_send(writer)
                self._send_packet(writer.get_bytes(), msgs_ack)

            del self._need_confirmation[:]

    def receive(self, update_state):
        """Receives a single message from the connected endpoint.

           This method returns nothing, and will only affect other parts
           of the MtProtoSender such as the updates callback being fired
           or a pending request being confirmed.

           Any unhandled object (likely updates) will be passed to
           update_state.process(TLObject).
        """
        with self._recv_lock:
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
                for r in self._pending_receive:
                    r.confirm_received.set()
                self._pending_receive.clear()
                return

        message, remote_msg_id, remote_seq = self._decode_msg(body)
        with BinaryReader(message) as reader:
            self._process_msg(remote_msg_id, remote_seq, reader, update_state)

    # endregion

    # region Low level processing

    def _send_packet(self, packet, request):
        """Sends the given packet bytes with the additional
           information of the original request.
        """
        request.request_msg_id = self.session.get_new_msg_id()

        # First calculate plain_text to encrypt it
        with BinaryWriter() as plain_writer:
            plain_writer.write_long(self.session.salt, signed=False)
            plain_writer.write_long(self.session.id, signed=False)
            plain_writer.write_long(request.request_msg_id)
            plain_writer.write_int(
                self.session.generate_sequence(request.content_related))

            plain_writer.write_int(len(packet))
            plain_writer.write(packet)

            msg_key = utils.calc_msg_key(plain_writer.get_bytes())

            key, iv = utils.calc_key(self.session.auth_key.key, msg_key, True)
            cipher_text = AES.encrypt_ige(plain_writer.get_bytes(), key, iv)

        # And then finally send the encrypted packet
        with BinaryWriter() as cipher_writer:
            cipher_writer.write_long(
                self.session.auth_key.key_id, signed=False)
            cipher_writer.write(msg_key)
            cipher_writer.write(cipher_text)
            with self._send_lock:
                self.connection.send(cipher_writer.get_bytes())

    def _decode_msg(self, body):
        """Decodes an received encrypted message body bytes"""
        message = None
        remote_msg_id = None
        remote_sequence = None

        with BinaryReader(body) as reader:
            if len(body) < 8:
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
        self._need_confirmation.append(msg_id)

        code = reader.read_int(signed=False)
        reader.seek(-4)

        # The following codes are "parsed manually"
        if code == 0xf35c6d01:  # rpc_result, (response of an RPC call)
            return self._handle_rpc_result(msg_id, sequence, reader)

        if code == 0x347773c5:  # pong
            return self._handle_pong(msg_id, sequence, reader)

        if code == 0x73f1f8dc:  # msg_container
            return self._handle_container(msg_id, sequence, reader, state)

        if code == 0x3072cfa1:  # gzip_packed
            return self._handle_gzip_packed(msg_id, sequence, reader, state)

        if code == 0xedab447b:  # bad_server_salt
            return self._handle_bad_server_salt(msg_id, sequence, reader)

        if code == 0xa7eff811:  # bad_msg_notification
            return self._handle_bad_msg_notification(msg_id, sequence, reader)

        # msgs_ack, it may handle the request we wanted
        if code == 0x62d6b459:
            ack = reader.tgread_object()
            for r in self._pending_receive:
                if r.request_msg_id in ack.msg_ids:
                    self._logger.debug('Ack found for the a request')

                    if self.logging_out:
                        self._logger.debug('Message ack confirmed a request')
                        self._pending_receive.remove(r)
                        r.confirm_received.set()

            return True

        # If the code is not parsed manually then it should be a TLObject.
        if code in tlobjects:
            result = reader.tgread_object()
            if state is None:
                self._logger.debug(
                    'Ignoring unhandled TLObject %s', repr(result)
                )
            else:
                self._logger.debug(
                    'Processing TLObject %s', repr(result)
                )
                state.process(result)

            return True

        self._logger.debug('Unknown message: {}'.format(hex(code)))
        return False

    # endregion

    # region Message handling

    def _pop_request(self, request_msg_id):
        """Pops a pending request from self._pending_receive, or
           returns None if it's not found
        """
        for i in range(len(self._pending_receive)):
            if self._pending_receive[i].request_msg_id == request_msg_id:
                return self._pending_receive.pop(i)

    def _handle_pong(self, msg_id, sequence, reader):
        self._logger.debug('Handling pong')
        reader.read_int(signed=False)  # code
        received_msg_id = reader.read_long()

        request = self._pop_request(received_msg_id)
        if request:
            self._logger.debug('Pong confirmed a request')
            request.confirm_received.set()

        return True

    def _handle_container(self, msg_id, sequence, reader, state):
        self._logger.debug('Handling container')
        reader.read_int(signed=False)  # code
        size = reader.read_int()
        for _ in range(size):
            inner_msg_id = reader.read_long()
            reader.read_int()  # inner_sequence
            inner_length = reader.read_int()
            begin_position = reader.tell_position()

            # Note that this code is IMPORTANT for skipping RPC results of
            # lost requests (i.e., ones from the previous connection session)
            try:
                if not self._process_msg(inner_msg_id, sequence, reader, state):
                    reader.set_position(begin_position + inner_length)
            except:
                # If any error is raised, something went wrong; skip the packet
                reader.set_position(begin_position + inner_length)
                raise

        return True

    def _handle_bad_server_salt(self, msg_id, sequence, reader):
        self._logger.debug('Handling bad server salt')
        reader.read_int(signed=False)  # code
        bad_msg_id = reader.read_long()
        reader.read_int()  # bad_msg_seq_no
        reader.read_int()  # error_code
        new_salt = reader.read_long(signed=False)
        self.session.salt = new_salt

        request = self._pop_request(bad_msg_id)
        if request:
            self.send(request)

        return True

    def _handle_bad_msg_notification(self, msg_id, sequence, reader):
        self._logger.debug('Handling bad message notification')
        reader.read_int(signed=False)  # code
        reader.read_long()  # request_id
        reader.read_int()  # request_sequence

        error_code = reader.read_int()
        error = BadMessageError(error_code)
        if error_code in (16, 17):
            # sent msg_id too low or too high (respectively).
            # Use the current msg_id to determine the right time offset.
            self.session.update_time_offset(correct_msg_id=msg_id)
            self.session.save()
            self._logger.debug('Read Bad Message error: ' + str(error))
            self._logger.debug('Attempting to use the correct time offset.')
            return True
        elif error_code == 32:
            # msg_seqno too low, so just pump it up by some "large" amount
            # TODO A better fix would be to start with a new fresh session ID
            self.session._sequence += 64
            return True
        elif error_code == 33:
            # msg_seqno too high never seems to happen but just in case
            self.session._sequence -= 16
            return True
        else:
            raise error

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
                    report_method=type(request).constructor_id
                )
            else:
                error = rpc_message_to_error(
                    reader.read_int(), reader.tgread_string()
                )

            # Acknowledge that we received the error
            self._need_confirmation.append(request_id)
            self._send_acknowledges()

            if request:
                request.rpc_error = error
                request.confirm_received.set()
            # else TODO Where should this error be reported?
            # Read may be async. Can an error not-belong to a request?
            self._logger.debug('Read RPC error: %s', str(error))
        else:
            if request:
                self._logger.debug('Reading request response')
                if inner_code == 0x3072cfa1:  # GZip packed
                    unpacked_data = gzip.decompress(reader.tgread_bytes())
                    with BinaryReader(unpacked_data) as compressed_reader:
                        request.on_response(compressed_reader)
                else:
                    reader.seek(-4)
                    request.on_response(reader)

                request.confirm_received.set()
                return True
            else:
                # If it's really a result for RPC from previous connection
                # session, it will be skipped by the handle_container()
                self._logger.debug('Lost request will be skipped.')
                return False

    def _handle_gzip_packed(self, msg_id, sequence, reader, state):
        self._logger.debug('Handling gzip packed data')
        reader.read_int(signed=False)  # code
        packed_data = reader.tgread_bytes()
        unpacked_data = gzip.decompress(packed_data)

        with BinaryReader(unpacked_data) as compressed_reader:
            return self._process_msg(msg_id, sequence, compressed_reader, state)

    # endregion
