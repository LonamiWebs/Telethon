import re
import zlib
import pyaes
from time import sleep

from utils.binary_writer import BinaryWriter
from utils.binary_reader import BinaryReader
from requests.ack_request import AckRequest
import utils.helpers as helpers


class MtProtoSender:
    def __init__(self, transport, session):
        self._transport = transport
        self._session = session

        self.need_confirmation = []

    def change_transport(self, transport):
        self._transport = transport

    def generate_sequence(self, confirmed):
        if confirmed:
            result = self._session.sequence * 2 + 1
            self._session.sequence += 1
            return result
        else:
            return self._session.sequence * 2

    # TODO async?
    def send(self, request):
        if self.need_confirmation:
            ack_request = AckRequest(self.need_confirmation)

            with BinaryWriter() as writer:
                ack_request.on_send(writer)
                self.send_packet(writer.get_bytes(), ack_request)
                del self.need_confirmation[:]

        with BinaryWriter() as writer:
            request.on_send(writer)
            self.send_packet(writer.get_bytes(), request)

        self._session.save()

    def send_packet(self, packet, request):
        request.message_id = self._session.get_new_msg_id()

        with BinaryWriter() as writer:
            # TODO Is there any difference with unsigned long and long?
            writer.write_long(self._session.salt, signed=False)
            writer.write_long(self._session.id, signed=False)
            writer.write_long(request.message_id)
            writer.write_int(self.generate_sequence(request.confirmed))
            writer.write_int(len(packet))
            writer.write(packet)

            msg_key = helpers.calc_msg_key(writer.get_bytes())

            key, iv = helpers.calc_key(self._session.auth_key.data, msg_key, True)
            aes = pyaes.AESModeOfOperationCFB(key, iv, 16)
            cipher_text = aes.encrypt(writer.get_bytes())

        with BinaryWriter() as writer:
            # TODO is it unsigned long?
            writer.write_long(self._session.auth_key.id, signed=False)
            writer.write(msg_key)
            writer.write(cipher_text)

            self._transport.send(writer.get_bytes())

    def decode_msg(self, body):
        message = None
        remote_message_id = None
        remote_sequence = None

        with BinaryReader(body) as reader:
            if len(body) < 8:
                raise BufferError("Can't decode packet")

            # TODO Check for both auth key ID and msg_key correctness
            remote_auth_key_id = reader.read_long()
            msg_key = reader.read(16)

            key, iv = helpers.calc_key(self._session.auth_key.data, msg_key, False)
            aes = pyaes.AESModeOfOperationCFB(key, iv, 16)
            plain_text = aes.decrypt(reader.read(len(body) - reader.tell_position()))

            with BinaryReader(plain_text) as plain_text_reader:
                remote_salt = plain_text_reader.read_long()
                remote_session_id = plain_text_reader.read_long()
                remote_message_id = plain_text_reader.read_long()
                remote_sequence = plain_text_reader.read_int()
                msg_len = plain_text_reader.read_int()
                message = plain_text_reader.read(msg_len)

        return message, remote_message_id, remote_sequence

    def receive(self, mtproto_request):
        while not mtproto_request.confirm_received:
            message, remote_message_id, remote_sequence = self.decode_msg(self._transport.receive().body)

            with BinaryReader(message) as reader:
                self.process_msg(remote_message_id, remote_sequence, reader, mtproto_request)

    def process_msg(self, message_id, sequence, reader, mtproto_request):
        # TODO Check salt, session_id and sequence_number
        self.need_confirmation.append(message_id)

        code = reader.read_int(signed=False)
        reader.seek(-4)

        if code == 0x73f1f8dc:  # Container
            return self.handle_container(message_id, sequence, reader, mtproto_request)
        if code == 0x7abe77ec:  # Ping
            return self.handle_ping(message_id, sequence, reader)
        if code == 0x347773c5:  # pong
            return self.handle_pong(message_id, sequence, reader)
        if code == 0xae500895:  # future_salts
            return self.handle_future_salts(message_id, sequence, reader)
        if code == 0x9ec20908:  # new_session_created
            return self.handle_new_session_created(message_id, sequence, reader)
        if code == 0x62d6b459:  # msgs_ack
            return self.handle_msgs_ack(message_id, sequence, reader)
        if code == 0xedab447b:  # bad_server_salt
            return self.handle_bad_server_salt(message_id, sequence, reader, mtproto_request)
        if code == 0xa7eff811:  # bad_msg_notification
            return self.handle_bad_msg_notification(message_id, sequence, reader)
        if code == 0x276d3ec6:  # msg_detailed_info
            return self.hangle_msg_detailed_info(message_id, sequence, reader)
        if code == 0xf35c6d01:  # rpc_result
            return self.handle_rpc_result(message_id, sequence, reader, mtproto_request)
        if code == 0x3072cfa1:  # gzip_packed
            return self.handle_gzip_packed(message_id, sequence, reader, mtproto_request)

        if (code == 0xe317af7e or
                    code == 0xd3f45784 or
                    code == 0x2b2fbd4e or
                    code == 0x78d4dec1 or
                    code == 0x725b04c3 or
                    code == 0x74ae4240):
            return self.handle_update(message_id, sequence, reader)

        # TODO Log unknown message code
        return False

    def handle_update(self, message_id, sequence, reader):
        return False

    def handle_container(self, message_id, sequence, reader, mtproto_request):
        code = reader.read_int(signed=False)
        size = reader.read_int()
        for _ in range(size):
            inner_msg_id = reader.read_long(signed=False)
            inner_sequence = reader.read_int()
            inner_length = reader.read_int()
            begin_position = reader.tell_position()
            try:
                if not self.process_msg(inner_msg_id, sequence, reader, mtproto_request):
                    reader.set_position(begin_position + inner_length)

            except:
                reader.set_position(begin_position + inner_length)

        return False

    def handle_ping(self, message_id, sequence, reader):
        return False

    def handle_pong(self, message_id, sequence, reader):
        return False

    def handle_future_salts(self, message_id, sequence, reader):
        code = reader.read_int(signed=False)
        request_id = reader.read_long(signed=False)
        reader.seek(-12)

        raise NotImplementedError("Handle future server salts function isn't implemented.")

    def handle_new_session_created(self, message_id, sequence, reader):
        return False

    def handle_msgs_ack(self, message_id, sequence, reader):
        return False

    def handle_bad_server_salt(self, message_id, sequence, reader, mtproto_request):
        code = reader.read_int(signed=False)
        bad_msg_id = reader.read_long(signed=False)
        bad_msg_seq_no = reader.read_int()
        error_code = reader.read_int()
        new_salt = reader.read_long(signed=False)

        self._session.salt = new_salt

        # Resend
        self.send(mtproto_request)

        return True

    def handle_bad_msg_notification(self, message_id, sequence, reader):
        code = reader.read_int(signed=False)
        request_id = reader.read_long(signed=False)
        request_sequence = reader.read_int()
        error_code = reader.read_int()

        if error_code == 16:
            raise RuntimeError("msg_id too low (most likely, client time is wrong it would be worthwhile to "
                               "synchronize it using msg_id notifications and re-send the original message "
                               "with the “correct” msg_id or wrap it in a container with a new msg_id if the "
                               "original message had waited too long on the client to be transmitted)")
        if error_code == 17:
            raise RuntimeError("msg_id too high (similar to the previous case, the client time has to be "
                               "synchronized, and the message re-sent with the correct msg_id)")
        if error_code == 18:
            raise RuntimeError("Incorrect two lower order msg_id bits (the server expects client message msg_id "
                               "to be divisible by 4)")
        if error_code == 19:
            raise RuntimeError("Container msg_id is the same as msg_id of a previously received message "
                               "(this must never happen)")
        if error_code == 20:
            raise RuntimeError("Message too old, and it cannot be verified whether the server has received a "
                               "message with this msg_id or not")
        if error_code == 32:
            raise RuntimeError("msg_seqno too low (the server has already received a message with a lower "
                               "msg_id but with either a higher or an equal and odd seqno)")
        if error_code == 33:
            raise RuntimeError("msg_seqno too high (similarly, there is a message with a higher msg_id but with "
                               "either a lower or an equal and odd seqno)")
        if error_code == 34:
            raise RuntimeError("An even msg_seqno expected (irrelevant message), but odd received")
        if error_code == 35:
            raise RuntimeError("Odd msg_seqno expected (relevant message), but even received")
        if error_code == 48:
            raise RuntimeError("Incorrect server salt (in this case, the bad_server_salt response is received with "
                               "the correct salt, and the message is to be re-sent with it)")
        if error_code == 64:
            raise RuntimeError("Invalid container")

        raise NotImplementedError('This should never happen!')

    def hangle_msg_detailed_info(self, message_id, sequence, reader):
        return False

    def handle_rpc_result(self, message_id, sequence, reader, mtproto_request):
        code = reader.read_int(signed=False)
        request_id = reader.read_long(signed=False)

        if request_id == mtproto_request.message_id:
            mtproto_request.confirm_received = True

        inner_code = reader.read_int(signed=False)
        if inner_code == 0x2144ca19:  # RPC Error
            error_code = reader.read_int()
            error_msg = reader.tgread_string()

            if error_msg.startswith('FLOOD_WAIT_'):
                seconds = int(re.search(r'\d+', error_msg).group(0))
                print('Should wait {}s. Sleeping until then.')
                sleep(seconds)

            elif error_msg.startswith('PHONE_MIGRATE_'):
                dc_index = int(re.search(r'\d+', error_msg).group(0))
                raise ConnectionError('Your phone number registered to {} dc. Please update settings. '
                                      'See https://github.com/sochix/TLSharp#i-get-an-error-migrate_x '
                                      'for details.'.format(dc_index))
            else:
                raise ValueError(error_msg)

        elif inner_code == 0x3072cfa1:  # GZip packed
            try:
                packed_data = reader.tgread_bytes()
                unpacked_data = zlib.decompress(packed_data)

                with BinaryReader(unpacked_data) as compressed_reader:
                    mtproto_request.on_response(compressed_reader)

            except:
                pass

        else:
            reader.seek(-4)
            mtproto_request.on_response(reader)

    def handle_gzip_packed(self, message_id, sequence, reader, mtproto_request):
        code = reader.read_int(signed=False)
        packed_data = reader.tgread_bytes()
        unpacked_data = zlib.decompress(packed_data)

        with BinaryReader(unpacked_data) as compressed_reader:
            self.process_msg(message_id, sequence, compressed_reader, mtproto_request)
