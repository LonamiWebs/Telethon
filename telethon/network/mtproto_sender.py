import gzip
from datetime import timedelta
from threading import Event, RLock, Thread
from time import sleep, time

import telethon.helpers as utils
from telethon.crypto import AES
from telethon.errors import *
from telethon.log import Log
from telethon.tl.all_tlobjects import tlobjects
from telethon.tl.functions.updates import GetStateRequest
from telethon.tl.types import MsgsAck
from telethon.tl.functions import PingRequest
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
        self.waiting_receive = Event()

        # Used when logging out, the only request that seems to use 'ack' requests
        # TODO There might be a better way to handle msgs_ack requests
        self.logging_out = False

        self.ping_interval = 60
        self.ping_time_last = time()

        # Flags used to determine the status of the updates thread.
        self.updates_thread_running = Event()
        self.updates_thread_receiving = Event()

        # Sleep amount on "must sleep" error for the updates thread to sleep too
        self.updates_thread_sleep = None

        self.updates_thread = Thread(
            name='UpdatesThread', daemon=True,
            target=self.updates_thread_method)

        self.connect()

    def connect(self):
        """Connects to the server"""
        self.transport.connect()
        # The "updates" thread must also be running to make periodic ping requests.
        self.set_updates_thread(running=True)

    def disconnect(self):
        """Disconnects and **stops all the running threads** if any"""
        self.set_updates_thread(running=False)
        self.transport.close()

    def reconnect(self):
        """Disconnects and connects again (effectively reconnecting)"""
        self.disconnect()
        self.connect()

    def add_update_handler(self, handler):
        """Adds an update handler (a method with one argument, the received
           TLObject) that is fired when there are updates available"""

        # The updates thread is already running for periodic ping requests,
        # so there is no need to start it when adding update handlers.
        self.on_update_handlers.append(handler)

    def remove_update_handler(self, handler):
        self.on_update_handlers.remove(handler)

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

    def send_ping(self):
        """Sends PingRequest"""
        request = PingRequest(utils.generate_random_long())
        self.send(request)
        self.receive(request)

    def send(self, request):
        """Sends the specified MTProtoRequest, previously sending any message
           which needed confirmation. This also pauses the updates thread"""

        # Only cancel the receive *if* it was the
        # updates thread who was receiving. We do
        # not want to cancel other pending requests!
        if self.updates_thread_receiving.is_set():
            Log.i('Cancelling updates receive from send()...')
            self.transport.cancel_receive()

        # Now only us can be using this method
        with self.lock:
            Log.d('send() acquired the lock')
            # Set the flag to true so the updates thread stops trying to receive
            self.waiting_receive.set()

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

        Log.d('send() released the lock')

    def receive(self, request, timeout=timedelta(seconds=5)):
        """Receives the specified MTProtoRequest ("fills in it"
           the received data). This also restores the updates thread.
           An optional timeout can be specified to cancel the operation
           if no data has been read after its time delta"""

        with self.lock:
            Log.d('receive() acquired the lock')
            # Don't stop trying to receive until we get the request we wanted
            while not request.confirm_received:
                Log.i('Trying to .receive() the request result...')
                seq, body = self.transport.receive(timeout)
                message, remote_msg_id, remote_sequence = self.decode_msg(body)

                with BinaryReader(message) as reader:
                    self.process_msg(remote_msg_id, remote_sequence, reader,
                                     request)

            Log.i('Request result received')

            # We can now set the flag to False thus resuming the updates thread
            self.waiting_receive.clear()
        Log.d('receive() released the lock')

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
        if code == 0x62d6b459:
            ack = reader.tgread_object()
            if request and request.msg_id in ack.msg_ids:
                Log.w('Ack found for the current request ID')

                if self.logging_out:
                    Log.i('Message ack confirmed the logout request')
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
        Log.d('Handling update for object %s', repr(tlobject))
        for handler in self.on_update_handlers:
            handler(tlobject)

        return False

    def handle_pong(self, msg_id, sequence, reader, request):
        Log.d('Handling pong')
        reader.read_int(signed=False)  # code
        recv_msg_id = reader.read_long(signed=False)

        if recv_msg_id == request.msg_id:
            Log.w('Pong confirmed a request')
            request.confirm_received = True

        return False

    def handle_container(self, msg_id, sequence, reader, request):
        Log.d('Handling container')
        reader.read_int(signed=False)  # code
        size = reader.read_int()
        for _ in range(size):
            inner_msg_id = reader.read_long(signed=False)
            reader.read_int()  # inner_sequence
            inner_length = reader.read_int()
            begin_position = reader.tell_position()

            # note: this code is IMPORTANT for skipping RPC results of lost
            # requests (for example, ones from the previous connection session)
            if not self.process_msg(inner_msg_id, sequence, reader, request):
                reader.set_position(begin_position + inner_length)

        return False

    def handle_bad_server_salt(self, msg_id, sequence, reader, request):
        Log.d('Handling bad server salt')
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
        Log.d('Handling bad message notification')
        reader.read_int(signed=False)  # code
        reader.read_long(signed=False)  # request_id
        reader.read_int()  # request_sequence

        error_code = reader.read_int()
        raise BadMessageError(error_code)

    def handle_rpc_result(self, msg_id, sequence, reader, request):
        Log.d('Handling RPC result, request is%s None', ' not' if request else '')
        reader.read_int(signed=False)  # code
        request_id = reader.read_long(signed=False)
        inner_code = reader.read_int(signed=False)

        if request and request_id == request.msg_id:
            request.confirm_received = True

        if inner_code == 0x2144ca19:  # RPC Error
            error = RPCError(
                code=reader.read_int(), message=reader.tgread_string())

            Log.w('Read RPC error: %s', str(error))
            if error.must_resend:
                if not request:
                    raise ValueError(
                        'The previously sent request must be resent. '
                        'However, no request was previously sent (called from updates thread).')
                request.confirm_received = False

            if error.message.startswith('FLOOD_WAIT_'):
                self.updates_thread_sleep = error.additional_data

                print('Should wait {}s. Sleeping until then.'.format(
                    error.additional_data))
                sleep(error.additional_data)

            elif '_MIGRATE_' in error.message:
                raise InvalidDCError(error.additional_data)

            else:
                raise error
        else:
            if not request:
                raise ValueError(
                    'Cannot receive a request from inside an RPC result from the updates thread.')

            Log.d('Reading request response')
            if inner_code == 0x3072cfa1:  # GZip packed
                unpacked_data = gzip.decompress(reader.tgread_bytes())
                with BinaryReader(unpacked_data) as compressed_reader:
                    request.on_response(compressed_reader)
            else:
                reader.seek(-4)
                if request_id == request.msg_id:
                    request.on_response(reader)
                else:
                    # note: if it's really a result for RPC from previous connection
                    # session, it will be skipped by the handle_container()
                    Log.w('RPC result found for unknown request (maybe from previous connection session)')

    def handle_gzip_packed(self, msg_id, sequence, reader, request):
        Log.d('Handling gzip packed data')
        reader.read_int(signed=False)  # code
        packed_data = reader.tgread_bytes()
        unpacked_data = gzip.decompress(packed_data)

        with BinaryReader(unpacked_data) as compressed_reader:
            return self.process_msg(msg_id, sequence, compressed_reader,
                                    request)

    # endregion

    def set_updates_thread(self, running):
        """Sets the updates thread status (running or not)"""
        if running == self.updates_thread_running.is_set():
            return

        # Different state, update the saved value and behave as required
        Log.i('Changing updates thread running status to %s', running)
        if running:
            self.updates_thread_running.set()
            self.updates_thread.start()
        else:
            self.updates_thread_running.clear()
            if self.updates_thread_receiving.is_set():
                self.transport.cancel_receive()

    def updates_thread_method(self):
        """This method will run until specified and listen for incoming updates"""

        # Set a reasonable timeout when checking for updates
        timeout = timedelta(minutes=1)

        while self.updates_thread_running.is_set():
            # Always sleep a bit before each iteration to relax the CPU,
            # since it's possible to early 'continue' the loop to reach
            # the next iteration, but we still should to sleep.
            if self.updates_thread_sleep:
                sleep(self.updates_thread_sleep)
                self.updates_thread_sleep = None
            else:
                # Longer sleep if we're not expecting updates (only pings)
                sleep(0.1 if self.on_update_handlers else 1)

            # Only try to receive updates if we're not waiting to receive a request
            if not self.waiting_receive.is_set():
                with self.lock:
                    Log.d('Updates thread acquired the lock')
                    try:
                        now = time()
                        # If ping_interval seconds passed since last ping, send a new one
                        if now >= self.ping_time_last + self.ping_interval:
                            self.ping_time_last = now
                            self.send_ping()
                            Log.d('Ping sent from the updates thread')

                        # Exit the loop if we're not expecting to receive any updates
                        if not self.on_update_handlers:
                            Log.d('No updates handlers found, continuing')
                            continue

                        self.updates_thread_receiving.set()
                        Log.d('Trying to receive updates from the updates thread')
                        seq, body = self.transport.receive(timeout)
                        message, remote_msg_id, remote_sequence = self.decode_msg(
                            body)

                        Log.i('Received update from the updates thread')
                        with BinaryReader(message) as reader:
                            self.process_msg(remote_msg_id, remote_sequence,
                                             reader)

                    except TimeoutError:
                        Log.d('Receiving updates timed out')
                        # TODO Workaround for issue #50
                        r = GetStateRequest()
                        try:
                            Log.d('Sending GetStateRequest (workaround for issue #50)')
                            self.send(r)
                            self.receive(r)
                        except TimeoutError:
                            Log.w('Timed out inside a timeout, trying to reconnect...')
                            self.reconnect()
                            self.send(r)
                            self.receive(r)

                    except ReadCancelledError:
                        Log.i('Receiving updates cancelled')
                    except OSError:
                        Log.w('OSError on updates thread, %s logging out',
                              'was' if self.logging_out else 'was not')

                        if self.logging_out:
                            # This error is okay when logging out, means we got disconnected
                            # TODO Not sure why this happens because we call disconnect()…
                            self.set_updates_thread(running=False)
                        else:
                            raise

                Log.d('Updates thread released the lock')
                self.updates_thread_receiving.clear()
