# This file is based on TLSharp
# https://github.com/sochix/TLSharp/blob/master/TLSharp.Core/TelegramClient.cs
from network.mtproto_sender import MtProtoSender
from network.tcp_transport import TcpTransport
import network.authenticator as authenticator
from tl.session import Session
import utils.helpers as utils
import platform
import re

from tl.functions.invoke_with_layer import InvokeWithLayer
from tl.functions.init_connection import InitConnection
from tl.functions.help.get_config import GetConfig
from tl.functions.auth.check_phone import CheckPhone
from tl.functions.auth.send_code import SendCode
from tl.functions.auth.sign_in import SignIn
from tl.functions.contacts.get_contacts import GetContacts
from tl.types.input_peer_user import InputPeerUser
from tl.functions.messages.send_message import SendMessage


class TelegramClient:

    def __init__(self, session_user_id, layer, api_id=None, api_hash=None):
        if api_id is None or api_hash is None:
            raise PermissionError('Your API ID or Hash are invalid. Make sure to obtain yours in http://my.telegram.org')

        self.api_id = api_id
        self.api_hash = api_hash

        self.layer = layer

        self.session = Session.try_load_or_create_new(session_user_id)
        self.transport = TcpTransport(self.session.server_address, self.session.port)
        self.dc_options = None

    # TODO Should this be async?
    def connect(self, reconnect=False):
        if self.session.auth_key is None or reconnect:
            self.session.auth_key, self.session.time_offset= authenticator.do_authentication(self.transport)

        self.sender = MtProtoSender(self.transport, self.session)

        if not reconnect:
            request = InvokeWithLayer(layer=self.layer,
                                      query=InitConnection(api_id=self.api_id,
                                                           device_model=platform.node(),
                                                           system_version=platform.system(),
                                                           app_version='0.1',
                                                           lang_code='en',
                                                           query=GetConfig()))

            self.sender.send(request)
            self.sender.receive(request)

            # Result is a Config TLObject
            self.dc_options = request.result.dc_options

        return True

    def reconnect_to_dc(self, dc_id):
        if self.dc_options is None or not self.dc_options:
            raise ConnectionError("Can't reconnect. Stabilise an initial connection first.")

        # dc is a DcOption TLObject
        dc = next(dc for dc in self.dc_options if dc.id == dc_id)

        self.transport = TcpTransport(dc.ip_address, dc.port)
        self.session.server_address = dc.ip_address
        self.session.port = dc.port

        self.connect(reconnect=True)

    def is_user_authorized(self):
        return self.session.user is not None

    def is_phone_registered(self, phone_number):
        assert self.sender is not None, 'Not connected!'

        request = CheckPhone(phone_number)
        self.sender.send(request)
        self.sender.receive(request)

        # Result is an Auth.CheckedPhone
        return request.result.phone_registered

    def send_code_request(self, phone_number, destination='code'):
        if destination == 'code':
            destination = 5
        elif destination == 'sms':
            destination = 0
        else:
            raise ValueError('Destination must be either "code" or "sms"')

        request = SendCode(phone_number, self.api_id, self.api_hash)
        completed = False
        while not completed:
            try:
                self.sender.send(request)
                self.sender.receive(request)
                completed = True
            except ConnectionError as error:
                if str(error).startswith('Your phone number is registered to'):
                    dc = int(re.search(r'\d+', str(error)).group(0))
                    self.reconnect_to_dc(dc)
                else:
                    raise error

        return request.result.phone_code_hash

    def make_auth(self, phone_number, phone_code_hash, code):
        request = SignIn(phone_number, phone_code_hash, code)
        self.sender.send(request)
        self.sender.receive(request)

        # Result is an Auth.Authorization TLObject
        self.session.user = request.result.user
        self.session.save()

        return self.session.user

    def import_contacts(self, phone_code_hash):
        request = GetContacts(phone_code_hash)
        self.sender.send(request)
        self.sender.receive(request)
        return request.result.contacts, request.result.users

    def send_message(self, user, message):
        peer = InputPeerUser(user.id, user.access_hash)
        request = SendMessage(peer, message, utils.generate_random_long())

        self.sender.send(request)
        self.sender.send(request)
