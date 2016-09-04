# This file is based on TLSharp
# https://github.com/sochix/TLSharp/blob/master/TLSharp.Core/Network/MtProtoSender.cs
import re
import zlib
from time import sleep

import utils
from crypto import AES
from utils import BinaryWriter, BinaryReader
from tl.types import MsgsAck


class MtProtoSender:
    """MTProto Mobile Protocol sender (https://core.telegram.org/mtproto/description)"""
    def __init__(self, transport, session):
        self.transport = transport
        self.session = session
        self.need_confirmation = []  # Message IDs that need confirmation

    def generate_sequence(self, confirmed):
        """Generates the next sequence number, based on whether it was confirmed yet or not"""
        if confirmed:
            result = self.session.sequence * 2 + 1
            self.session.sequence += 1
            return result
        else:
            return self.session.sequence * 2

    # region Send and receive

    # TODO In TLSharp, this was async. Should this be?
    def send(self, request):
        """Sends the specified MTProtoRequest, previously sending any message which needed confirmation"""

        # First check if any message needs confirmation, if this is the case, send an "AckRequest"
        if self.need_confirmation:
            msgs_ack = MsgsAck(self.need_confirmation)
            with BinaryWriter() as writer:
                msgs_ack.on_send(writer)
                self.send_packet(writer.get_bytes(), msgs_ack)
                del self.need_confirmation[:]

        # Then send our packed request
        with BinaryWriter() as writer:
            request.on_send(writer)
            self.send_packet(writer.get_bytes(), request)

        # And update the saved session
        self.session.save()

    def receive(self, request):
        """Receives the specified MTProtoRequest ("fills in it" the received data)"""
        while not request.confirm_received:
            message, remote_msg_id, remote_sequence = self.decode_msg(self.transport.receive().body)

            with BinaryReader(message) as reader:
                self.process_msg(remote_msg_id, remote_sequence, reader, request)

    # endregion

    # region Low level processing

    def send_packet(self, packet, request):
        """Sends the given packet bytes with the additional information of the original request"""
        request.msg_id = self.session.get_new_msg_id()

        # First calculate the ciphered bit
        with BinaryWriter() as writer:
            writer.write_long(self.session.salt, signed=False)
            writer.write_long(self.session.id, signed=False)
            writer.write_long(request.msg_id)
            writer.write_int(self.generate_sequence(request.confirmed))
            writer.write_int(len(packet))
            writer.write(packet)

            msg_key = utils.calc_msg_key(writer.get_bytes())

            key, iv = utils.calc_key(self.session.auth_key.key, msg_key, True)
            cipher_text = AES.encrypt_ige(writer.get_bytes(), key, iv)

        # And then finally send the packet
        with BinaryWriter() as writer:
            writer.write_long(self.session.auth_key.key_id, signed=False)
            writer.write(msg_key)
            writer.write(cipher_text)

            self.transport.send(writer.get_bytes())

    def decode_msg(self, body):
        """Decodes an received encrypted message body bytes"""
        message = None
        remote_msg_id = None
        remote_sequence = None

        with BinaryReader(body) as reader:
            if len(body) < 8:
                raise BufferError("Can't decode packet ({})".format(body))

            # TODO Check for both auth key ID and msg_key correctness
            remote_auth_key_id = reader.read_long()
            msg_key = reader.read(16)

            key, iv = utils.calc_key(self.session.auth_key.data, msg_key, False)
            plain_text = AES.decrypt_ige(reader.read(len(body) - reader.tell_position()), key, iv)

            with BinaryReader(plain_text) as plain_text_reader:
                remote_salt = plain_text_reader.read_long()
                remote_session_id = plain_text_reader.read_long()
                remote_msg_id = plain_text_reader.read_long()
                remote_sequence = plain_text_reader.read_int()
                msg_len = plain_text_reader.read_int()
                message = plain_text_reader.read(msg_len)

        return message, remote_msg_id, remote_sequence

    def process_msg(self, msg_id, sequence, reader, request):
        """Processes and handles a Telegram message"""
        # TODO Check salt, session_id and sequence_number
        self.need_confirmation.append(msg_id)

        code = reader.read_int(signed=False)
        reader.seek(-4)

        if code == 0x73f1f8dc:  # Container
            return self.handle_container(msg_id, sequence, reader, request)
        if code == 0x7abe77ec:  # Ping
            return self.handle_ping(msg_id, sequence, reader)
        if code == 0x347773c5:  # pong
            return self.handle_pong(msg_id, sequence, reader)
        if code == 0xae500895:  # future_salts
            return self.handle_future_salts(msg_id, sequence, reader)
        if code == 0x9ec20908:  # new_session_created
            return self.handle_new_session_created(msg_id, sequence, reader)
        if code == 0x62d6b459:  # msgs_ack
            return self.handle_msgs_ack(msg_id, sequence, reader)
        if code == 0xedab447b:  # bad_server_salt
            return self.handle_bad_server_salt(msg_id, sequence, reader, request)
        if code == 0xa7eff811:  # bad_msg_notification
            return self.handle_bad_msg_notification(msg_id, sequence, reader)
        if code == 0x276d3ec6:  # msg_detailed_info
            return self.hangle_msg_detailed_info(msg_id, sequence, reader)
        if code == 0xf35c6d01:  # rpc_result
            return self.handle_rpc_result(msg_id, sequence, reader, request)
        if code == 0x3072cfa1:  # gzip_packed
            return self.handle_gzip_packed(msg_id, sequence, reader, request)

        if (code == 0xe317af7e or
            code == 0xd3f45784 or
            code == 0x2b2fbd4e or
            code == 0x78d4dec1 or
            code == 0x725b04c3 or
                code == 0x74ae4240):
            return self.handle_update(msg_id, sequence, reader)

        print('Unknown message: {}'.format(hex(msg_id)))
        return False

    # endregion

    # region Message handling

    def handle_update(self, msg_id, sequence, reader):
        return False

    def handle_container(self, msg_id, sequence, reader, request):
        code = reader.read_int(signed=False)
        size = reader.read_int()
        for _ in range(size):
            inner_msg_id = reader.read_long(signed=False)
            inner_sequence = reader.read_int()
            inner_length = reader.read_int()
            begin_position = reader.tell_position()
            try:
                if not self.process_msg(inner_msg_id, sequence, reader, request):
                    reader.set_position(begin_position + inner_length)

            except:
                reader.set_position(begin_position + inner_length)

        return False

    def handle_ping(self, msg_id, sequence, reader):
        return False

    def handle_pong(self, msg_id, sequence, reader):
        return False

    def handle_future_salts(self, msg_id, sequence, reader):
        code = reader.read_int(signed=False)
        request_id = reader.read_long(signed=False)
        reader.seek(-12)

        raise NotImplementedError("Handle future server salts function isn't implemented.")

    def handle_new_session_created(self, msg_id, sequence, reader):
        return False

    def handle_msgs_ack(self, msg_id, sequence, reader):
        return False

    def handle_bad_server_salt(self, msg_id, sequence, reader, mtproto_request):
        code = reader.read_int(signed=False)
        bad_msg_id = reader.read_long(signed=False)
        bad_msg_seq_no = reader.read_int()
        error_code = reader.read_int()
        new_salt = reader.read_long(signed=False)

        self.session.salt = new_salt

        # Resend
        self.send(mtproto_request)

        return True

    def handle_bad_msg_notification(self, msg_id, sequence, reader):
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

    def hangle_msg_detailed_info(self, msg_id, sequence, reader):
        return False

    def handle_rpc_result(self, msg_id, sequence, reader, mtproto_request):
        code = reader.read_int(signed=False)
        request_id = reader.read_long(signed=False)

        if request_id == mtproto_request.msg_id:
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
                raise ConnectionError('Your phone number is registered to {} DC. Please update settings. '
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

    def handle_gzip_packed(self, msg_id, sequence, reader, mtproto_request):
        code = reader.read_int(signed=False)
        packed_data = reader.tgread_bytes()
        unpacked_data = zlib.decompress(packed_data)

        with BinaryReader(unpacked_data) as compressed_reader:
            self.process_msg(msg_id, sequence, compressed_reader, mtproto_request)

    # endregion
    pass
