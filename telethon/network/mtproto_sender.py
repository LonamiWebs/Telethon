import gzip
from datetime import timedelta
from threading import RLock, Thread
from time import sleep

import telethon.helpers as utils
from telethon.crypto import AES
from telethon.errors import *
from telethon.tl.all_tlobjects import tlobjects
from telethon.tl.types import MsgsAck
from telethon.utils import BinaryReader, BinaryWriter


class MtProtoSender:
    """MTProto Mobile Protocol sender (https://core.telegram.org/mtproto/description)"""

    def __init__(self, transport, session):
        self.transport = transport
        self.session = session

        self.need_confirmation = []  # Message IDs that need confirmation
        self.on_update_handlers = []

        # Store an RLock instance to make this class safely multi-threaded
        self.lock = RLock()

        # Flag used to determine whether we've received a sent request yet or not
        # We need this to avoid using the updates thread if we're waiting to read
        self.waiting_receive = False

        self.updates_thread = Thread(
            target=self.updates_thread_method, name='Updates thread')
        self.updates_thread_running = False
        self.updates_thread_receiving = False

        # Determine whether the received acknowledge request confirm
        # our requests or not. This is not desired until we initialize
        # our connection, because it breaks things when we call InvokeWithLayer
        # TODO There might be a better way to handle msgs_ack requests
        self.ack_requests_confirm = False

    def disconnect(self):
        """Disconnects and **stops all the running threads** if any"""
        self.set_listen_for_updates(enabled=False)
        self.transport.close()

    def add_update_handler(self, handler):
        """Adds an update handler (a method with one argument, the received
           TLObject) that is fired when there are updates available"""

        first_handler = not self.on_update_handlers
        self.on_update_handlers.append(handler)

        # If this is the first added handler,
        # we must start the thread to receive updates
        if first_handler:
            self.set_listen_for_updates(enabled=True)

    def remove_update_handler(self, handler):
        self.on_update_handlers.remove(handler)

        # If there are no more update handlers, stop the thread
        if not self.on_update_handlers:
            self.set_listen_for_updates(False)

    def generate_sequence(self, confirmed):
        """Generates the next sequence number, based on whether it
           was confirmed yet or not"""
        if confirmed:
            result = self.session.sequence * 2 + 1
            self.session.sequence += 1
            return result
        else:
            return self.session.sequence * 2

    # region Send and receive

    def send(self, request):
        """Sends the specified MTProtoRequest, previously sending any message
           which needed confirmation. This also pauses the updates thread"""

        # Only cancel the receive *if* it was the
        # updates thread who was receiving. We do
        # not want to cancel other pending requests!
        if self.updates_thread_receiving:
            self.transport.cancel_receive()

        # Now only us can be using this method
        with self.lock:
            # Set the flag to true so the updates thread stops trying to receive
            self.waiting_receive = True

            # If any message needs confirmation send an AckRequest first
            if self.need_confirmation:
                msgs_ack = MsgsAck(self.need_confirmation)
                with BinaryWriter() as writer:
                    msgs_ack.on_send(writer)
                    self.send_packet(writer.get_bytes(), msgs_ack)

                del self.need_confirmation[:]

            # Finally send our packed request
            with BinaryWriter() as writer:
                request.on_send(writer)
                self.send_packet(writer.get_bytes(), request)

            # And update the saved session
            self.session.save()

    def receive(self, request, timeout=timedelta(seconds=5)):
        """Receives the specified MTProtoRequest ("fills in it"
           the received data). This also restores the updates thread.
           An optional timeout can be specified to cancel the operation
           if no data has been read after its time delta"""

        with self.lock:
            # Don't stop trying to receive until we get the request we wanted
            while not request.confirm_received:
                seq, body = self.transport.receive(timeout)
                message, remote_msg_id, remote_sequence = self.decode_msg(body)

                with BinaryReader(message) as reader:
                    self.process_msg(remote_msg_id, remote_sequence, reader,
                                     request)

            # We can now set the flag to False thus resuming the updates thread
            self.waiting_receive = False

    # endregion

    # region Low level processing

    def send_packet(self, packet, request):
        """Sends the given packet bytes with the additional
           information of the original request. This does NOT lock the threads!"""
        request.msg_id = self.session.get_new_msg_id()

        # First calculate plain_text to encrypt it
        with BinaryWriter() as plain_writer:
            plain_writer.write_long(self.session.salt, signed=False)
            plain_writer.write_long(self.session.id, signed=False)
            plain_writer.write_long(request.msg_id)
            plain_writer.write_int(self.generate_sequence(request.confirmed))
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
            self.transport.send(cipher_writer.get_bytes())

    def decode_msg(self, body):
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

    def process_msg(self, msg_id, sequence, reader, request=None):
        """Processes and handles a Telegram message"""

        # TODO Check salt, session_id and sequence_number
        self.need_confirmation.append(msg_id)

        code = reader.read_int(signed=False)
        reader.seek(-4)

        # The following codes are "parsed manually"
        if code == 0xf35c6d01:  # rpc_result, (response of an RPC call, i.e., we sent a request)
            return self.handle_rpc_result(msg_id, sequence, reader, request)

        if code == 0x347773c5:  # pong
            return self.handle_pong(msg_id, sequence, reader, request)
        if code == 0x73f1f8dc:  # msg_container
            return self.handle_container(msg_id, sequence, reader, request)
        if code == 0x3072cfa1:  # gzip_packed
            return self.handle_gzip_packed(msg_id, sequence, reader, request)
        if code == 0xedab447b:  # bad_server_salt
            return self.handle_bad_server_salt(msg_id, sequence, reader,
                                               request)
        if code == 0xa7eff811:  # bad_msg_notification
            return self.handle_bad_msg_notification(msg_id, sequence, reader)

        # msgs_ack, it may handle the request we wanted
        if self.ack_requests_confirm and code == 0x62d6b459:
            ack = reader.tgread_object()
            if request and request.msg_id in ack.msg_ids:
                request.confirm_received = True
            return False

        # If the code is not parsed manually, then it was parsed by the code generator!
        # In this case, we will simply treat the incoming TLObject as an Update,
        # if we can first find a matching TLObject
        if code in tlobjects.keys():
            return self.handle_update(msg_id, sequence, reader)

        print('Unknown message: {}'.format(hex(code)))
        return False

    # endregion

    # region Message handling

    def handle_update(self, msg_id, sequence, reader):
        tlobject = reader.tgread_object()
        for handler in self.on_update_handlers:
            handler(tlobject)

        return False

    def handle_pong(self, msg_id, sequence, reader, request):
        reader.read_int(signed=False)  # code
        recv_msg_id = reader.read_long(signed=False)

        if recv_msg_id == request.msg_id:
            request.confirm_received = True

        return False

    def handle_container(self, msg_id, sequence, reader, request):
        reader.read_int(signed=False)  # code
        size = reader.read_int()
        for _ in range(size):
            inner_msg_id = reader.read_long(signed=False)
            reader.read_int()  # inner_sequence
            inner_length = reader.read_int()
            begin_position = reader.tell_position()

            if not self.process_msg(inner_msg_id, sequence, reader, request):
                reader.set_position(begin_position + inner_length)

        return False

    def handle_bad_server_salt(self, msg_id, sequence, reader, request):
        reader.read_int(signed=False)  # code
        reader.read_long(signed=False)  # bad_msg_id
        reader.read_int()  # bad_msg_seq_no
        reader.read_int()  # error_code
        new_salt = reader.read_long(signed=False)

        self.session.salt = new_salt

        if request is None:
            raise ValueError(
                'Tried to handle a bad server salt with no request specified')

        # Resend
        self.send(request)

        return True

    def handle_bad_msg_notification(self, msg_id, sequence, reader):
        reader.read_int(signed=False)  # code
        reader.read_long(signed=False)  # request_id
        reader.read_int()  # request_sequence

        error_code = reader.read_int()
        raise BadMessageError(error_code)

    def handle_rpc_result(self, msg_id, sequence, reader, request):
        reader.read_int(signed=False)  # code
        request_id = reader.read_long(signed=False)
        inner_code = reader.read_int(signed=False)

        if request and request_id == request.msg_id:
            request.confirm_received = True

        if inner_code == 0x2144ca19:  # RPC Error
            error = RPCError(
                code=reader.read_int(), message=reader.tgread_string())
            if error.must_resend:
                if not request:
                    raise ValueError(
                        'The previously sent request must be resent. '
                        'However, no request was previously sent (called from updates thread).')
                request.confirm_received = False

            if error.message.startswith('FLOOD_WAIT_'):
                print('Should wait {}s. Sleeping until then.'.format(
                    error.additional_data))
                sleep(error.additional_data)

            elif error.message.startswith('PHONE_MIGRATE_'):
                raise InvalidDCError(error.additional_data)

            else:
                raise error
        else:
            if not request:
                raise ValueError(
                    'Cannot receive a request from inside an RPC result from the updates thread.')

            if inner_code == 0x3072cfa1:  # GZip packed
                unpacked_data = gzip.decompress(reader.tgread_bytes())
                with BinaryReader(unpacked_data) as compressed_reader:
                    request.on_response(compressed_reader)
            else:
                reader.seek(-4)
                request.on_response(reader)

    def handle_gzip_packed(self, msg_id, sequence, reader, request):
        reader.read_int(signed=False)  # code
        packed_data = reader.tgread_bytes()
        unpacked_data = gzip.decompress(packed_data)

        with BinaryReader(unpacked_data) as compressed_reader:
            return self.process_msg(msg_id, sequence, compressed_reader,
                                    request)

    # endregion

    def set_listen_for_updates(self, enabled):
        if enabled:
            if not self.updates_thread_running:
                self.updates_thread_running = True
                self.updates_thread_receiving = False

                self.updates_thread.start()
        else:
            self.updates_thread_running = False
            if self.updates_thread_receiving:
                self.transport.cancel_receive()

    def updates_thread_method(self):
        """This method will run until specified and listen for incoming updates"""

        # Set a reasonable timeout when checking for updates
        timeout = timedelta(minutes=1)

        while self.updates_thread_running:
            # Only try to receive updates if we're not waiting to receive a request
            if not self.waiting_receive:
                with self.lock:
                    try:
                        self.updates_thread_receiving = True
                        seq, body = self.transport.receive(timeout)
                        message, remote_msg_id, remote_sequence = self.decode_msg(
                            body)

                        with BinaryReader(message) as reader:
                            self.process_msg(remote_msg_id, remote_sequence,
                                             reader)

                    except (ReadCancelledError, TimeoutError):
                        pass

                self.updates_thread_receiving = False

            # If we are here, it is because the read was cancelled
            # Sleep a bit just to give enough time for the other thread
            # to acquire the lock. No need to sleep if we're not running anymore
            if self.updates_thread_running:
                sleep(0.1)
