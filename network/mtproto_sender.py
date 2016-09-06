# This file is based on TLSharp
# https://github.com/sochix/TLSharp/blob/master/TLSharp.Core/Network/MtProtoSender.cs
import gzip
from errors import *
from time import sleep

import utils
from crypto import AES
from utils import BinaryWriter, BinaryReader
from tl.types import MsgsAck
from tl.all_tlobjects import tlobjects


class MtProtoSender:
    """MTProto Mobile Protocol sender (https://core.telegram.org/mtproto/description)"""
    def __init__(self, transport, session):
        self.transport = transport
        self.session = session
        self.need_confirmation = []  # Message IDs that need confirmation
        self.on_update_handlers = []

    def add_update_handler(self, handler):
        """Adds an update handler (a method with one argument, the received TLObject)
        that is fired when there are updates available"""
        self.on_update_handlers.append(handler)

    def generate_sequence(self, confirmed):
        """Generates the next sequence number, based on whether it was confirmed yet or not"""
        if confirmed:
            result = self.session.sequence * 2 + 1
            self.session.sequence += 1
            return result
        else:
            return self.session.sequence * 2

    # region Send and receive

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
            cipher_writer.write_long(self.session.auth_key.key_id, signed=False)
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
            remote_auth_key_id = reader.read_long()
            msg_key = reader.read(16)

            key, iv = utils.calc_key(self.session.auth_key.key, msg_key, False)
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

        # The following codes are "parsed manually"
        if code == 0xf35c6d01:  # rpc_result
            return self.handle_rpc_result(msg_id, sequence, reader, request)
        elif code == 0x73f1f8dc:  # msg_container
            return self.handle_container(msg_id, sequence, reader, request)
        elif code == 0x3072cfa1:  # gzip_packed
            return self.handle_gzip_packed(msg_id, sequence, reader, request)
        elif code == 0xedab447b:  # bad_server_salt
            return self.handle_bad_server_salt(msg_id, sequence, reader, request)
        elif code == 0xa7eff811:  # bad_msg_notification
            return self.handle_bad_msg_notification(msg_id, sequence, reader)
        else:
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

    def handle_container(self, msg_id, sequence, reader, request):
        code = reader.read_int(signed=False)
        size = reader.read_int()
        for _ in range(size):
            inner_msg_id = reader.read_long(signed=False)
            inner_sequence = reader.read_int()
            inner_length = reader.read_int()
            begin_position = reader.tell_position()

            if not self.process_msg(inner_msg_id, sequence, reader, request):
                reader.set_position(begin_position + inner_length)

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
        raise BadMessageError(error_code)

    def handle_rpc_result(self, msg_id, sequence, reader, mtproto_request):
        code = reader.read_int(signed=False)
        request_id = reader.read_long(signed=False)
        inner_code = reader.read_int(signed=False)

        if request_id == mtproto_request.msg_id:
            mtproto_request.confirm_received = True

        if inner_code == 0x2144ca19:  # RPC Error
            error = RPCError(code=reader.read_int(), message=reader.tgread_string())
            if error.must_resend:
                mtproto_request.confirm_received = False

            if error.message.startswith('FLOOD_WAIT_'):
                print('Should wait {}s. Sleeping until then.'.format(error.additional_data))
                sleep(error.additional_data)

            elif error.message.startswith('PHONE_MIGRATE_'):
                raise InvalidDCError(error.additional_data)

            else:
                raise error

        else:
            if inner_code == 0x3072cfa1:  # GZip packed
                unpacked_data = gzip.decompress(reader.tgread_bytes())
                with BinaryReader(unpacked_data) as compressed_reader:
                    mtproto_request.on_response(compressed_reader)

            else:
                reader.seek(-4)
                mtproto_request.on_response(reader)

    def handle_gzip_packed(self, msg_id, sequence, reader, mtproto_request):
        code = reader.read_int(signed=False)
        packed_data = reader.tgread_bytes()
        unpacked_data = gzip.decompress(packed_data)

        with BinaryReader(unpacked_data) as compressed_reader:
            self.process_msg(msg_id, sequence, compressed_reader, mtproto_request)

    # endregion
    pass
