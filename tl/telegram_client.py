# This file is based on TLSharp
# https://github.com/sochix/TLSharp/blob/master/TLSharp.Core/TelegramClient.cs
import platform
from parser.markdown_parser import parse_message_entities

import utils
import network.authenticator
from network import MtProtoSender, TcpTransport
from errors import *

from tl import Session
from tl.types import PeerUser, PeerChat, PeerChannel, InputPeerUser, InputPeerChat, InputPeerChannel, InputPeerEmpty
from tl.functions import InvokeWithLayerRequest, InitConnectionRequest
from tl.functions.help import GetConfigRequest
from tl.functions.auth import CheckPhoneRequest, SendCodeRequest, SignInRequest
from tl.functions.messages import GetDialogsRequest, SendMessageRequest


class TelegramClient:

    # region Initialization

    def __init__(self, session_user_id, layer, api_id=None, api_hash=None):
        if api_id is None or api_hash is None:
            raise PermissionError('Your API ID or Hash are invalid. Please read "Requirements" on README.md')

        self.api_id = api_id
        self.api_hash = api_hash

        self.layer = layer

        self.session = Session.try_load_or_create_new(session_user_id)
        self.transport = TcpTransport(self.session.server_address, self.session.port)

        # These will be set later
        self.dc_options = None
        self.sender = None
        self.phone_code_hashes = {}

    # endregion

    # region Connecting

    def connect(self, reconnect=False):
        """Connects to the Telegram servers, executing authentication if required.
           Note that authenticating to the Telegram servers is not the same as authenticating
           the app, which requires to send a code first."""

        if not self.session.auth_key or reconnect:
            self.session.auth_key, self.session.time_offset = network.authenticator.do_authentication(self.transport)
            self.session.save()

        self.sender = MtProtoSender(self.transport, self.session)
        self.sender.add_update_handler(self.on_update)

        # Always init connection by using the latest layer, not only when not reconnecting (as in original TLSharp's)
        # Otherwise, the server thinks that were using the oldest layer!
        # (Note that this is mainly untested, but it seems like it since some errors point in that direction)
        request = InvokeWithLayerRequest(layer=self.layer,
                                         query=InitConnectionRequest(api_id=self.api_id,
                                                                     device_model=platform.node(),
                                                                     system_version=platform.system(),
                                                                     app_version='0.2',
                                                                     lang_code='en',
                                                                     query=GetConfigRequest()))

        self.sender.send(request)
        self.sender.receive(request)

        self.dc_options = request.result.dc_options
        return True

    def reconnect_to_dc(self, dc_id):
        """Reconnects to the specified DC ID. This is automatically called after an InvalidDCError is raised"""
        if self.dc_options is None or not self.dc_options:
            raise ConnectionError("Can't reconnect. Stabilise an initial connection first.")

        dc = next(dc for dc in self.dc_options if dc.id == dc_id)

        self.transport.close()
        self.transport = TcpTransport(dc.ip_address, dc.port)
        self.session.server_address = dc.ip_address
        self.session.port = dc.port
        self.session.save()

        self.connect(reconnect=True)

    # endregion

    # region Telegram requests functions

    def is_user_authorized(self):
        """Has the user been authorized yet (code request sent and confirmed)?
           Note that this will NOT yield the correct result if the session was revoked by another client!"""
        return self.session.user is not None

    def send_code_request(self, phone_number):
        """Sends a code request to the specified phone number"""
        request = SendCodeRequest(phone_number, self.api_id, self.api_hash)
        completed = False
        while not completed:
            try:
                self.sender.send(request)
                self.sender.receive(request)
                completed = True
                if request.result:
                    self.phone_code_hashes[phone_number] = request.result.phone_code_hash

            except InvalidDCError as error:
                self.reconnect_to_dc(error.new_dc)

    def make_auth(self, phone_number, code):
        """Completes the authorization of a phone number by providing the received code"""
        if phone_number not in self.phone_code_hashes:
            raise ValueError('Please make sure you have called send_code_request first.')

        # TODO Handle invalid code
        request = SignInRequest(phone_number, self.phone_code_hashes[phone_number], code)
        self.sender.send(request)
        self.sender.receive(request)

        # Result is an Auth.Authorization TLObject
        self.session.user = request.result.user
        self.session.save()

        return self.session.user

    def get_dialogs(self, count=10, offset_date=None, offset_id=0, offset_peer=InputPeerEmpty()):
        """Returns 'count' dialogs in a (dialog, display, input_peer) list format"""

        # Telegram wants the offset_date in an unix-timestamp format, not Python's datetime
        # However that's not very comfortable, so calculate the correct value here
        if offset_date is None:
            offset_date = 0
        else:
            offset_date = int(offset_date.timestamp())

        request = GetDialogsRequest(offset_date=offset_date,
                                    offset_id=offset_id,
                                    offset_peer=offset_peer,
                                    limit=count)

        self.sender.send(request)
        self.sender.receive(request)

        result = request.result
        return [(dialog,
                 TelegramClient.find_display_name(dialog.peer, result.users, result.chats),
                 TelegramClient.find_input_peer_name(dialog.peer, result.users, result.chats))
                for dialog in result.dialogs]

    def send_message(self, input_peer, message, markdown=False, no_web_page=False):
        """Sends a message to the given input peer"""
        if markdown:
            msg, entities = parse_message_entities(message)
        else:
            msg, entities = message, []

        request = SendMessageRequest(peer=input_peer,
                                     message=msg,
                                     random_id=utils.generate_random_long(),
                                     entities=entities,
                                     no_webpage=no_web_page)

        self.sender.send(request)
        self.sender.receive(request)

    # endregion

    # region Utilities

    @staticmethod
    def find_display_name(peer, users, chats):
        """Searches the display name for peer in both users and chats.
           Returns None if it was not found"""
        try:
            if type(peer) is PeerUser:
                user = next(u for u in users if u.id == peer.user_id)
                if user.last_name is not None:
                    return '{} {}'.format(user.first_name, user.last_name)
                return user.first_name

            elif type(peer) is PeerChat:
                return next(c for c in chats if c.id == peer.chat_id).title

            elif type(peer) is PeerChannel:
                return next(c for c in chats if c.id == peer.channel_id).title

        except StopIteration:
            pass

        return None

    @staticmethod
    def find_input_peer_name(peer, users, chats):
        """Searches the given peer in both users and chats and returns an InputPeer for it.
           Returns None if it was not found"""
        try:
            if type(peer) is PeerUser:
                user = next(u for u in users if u.id == peer.user_id)
                return InputPeerUser(user.id, user.access_hash)

            elif type(peer) is PeerChat:
                chat = next(c for c in chats if c.id == peer.chat_id)
                return InputPeerChat(chat.id)

            elif type(peer) is PeerChannel:
                channel = next(c for c in chats if c.id == peer.channel_id)
                return InputPeerChannel(channel.id, channel.access_hash)

        except StopIteration:
            pass

        return None

    # endregion

    # region Updates handling

    def on_update(self, tlobject):
        """This method is fired when there are updates from Telegram.
        Add your own implementation below, or simply override it!"""
        print('We have an update: {}'.format(str(tlobject)))

    # endregion
