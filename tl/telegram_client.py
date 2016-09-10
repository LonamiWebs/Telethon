# This file structure is based on TLSharp
# https://github.com/sochix/TLSharp/blob/master/TLSharp.Core/TelegramClient.cs
import platform

import utils
import network.authenticator

from errors import *
from network import MtProtoSender, TcpTransport
from parser.markdown_parser import parse_message_entities

# For sending and receiving requests
from tl import MTProtoRequest
from tl import Session
from tl.types import PeerUser, PeerChat, PeerChannel, InputPeerUser, InputPeerChat, InputPeerChannel, InputPeerEmpty
from tl.functions import InvokeWithLayerRequest, InitConnectionRequest
from tl.functions.help import GetConfigRequest
from tl.functions.auth import SendCodeRequest, SignInRequest
from tl.functions.messages import GetDialogsRequest, GetHistoryRequest, SendMessageRequest

# For working with updates
from tl.types import UpdateShortMessage


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
        try:
            if not self.session.auth_key or reconnect:
                self.session.auth_key, self.session.time_offset = \
                    network.authenticator.do_authentication(self.transport)

                self.session.save()

            self.sender = MtProtoSender(self.transport, self.session)
            self.sender.add_update_handler(self.on_update)

            # Now it's time to send an InitConnectionRequest
            # This must always be invoked with the layer we'll be using
            query = InitConnectionRequest(api_id=self.api_id,
                                          device_model=platform.node(),
                                          system_version=platform.system(),
                                          app_version='0.3',
                                          lang_code='en',
                                          query=GetConfigRequest())

            result = self.invoke(InvokeWithLayerRequest(layer=self.layer, query=query))

            # Only listen for updates if we're authorized
            if self.is_user_authorized():
                self.sender.set_listen_for_updates(True)

            # We're only interested in the DC options,
            # although many other options are available!
            self.dc_options = result.dc_options
            return True
        except RPCError as error:
            print('Could not stabilise initial connection: {}'.format(error))
            return False

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

    def disconnect(self):
        """Disconnects from the Telegram server **and pauses all the spawned threads**"""
        if self.sender:
            self.sender.disconnect()

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
                result = self.invoke(request)
                self.phone_code_hashes[phone_number] = result.phone_code_hash
                completed = True

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

        # Now that we're authorized, we can listen for incoming updates
        self.sender.set_listen_for_updates(True)

        return self.session.user

    def get_dialogs(self, count=10, offset_date=None, offset_id=0, offset_peer=InputPeerEmpty()):
        """Returns a tuple of lists ([dialogs], [displays], [input_peers]) with 'count' items each"""

        r = self.invoke(GetDialogsRequest(offset_date=TelegramClient.get_tg_date(offset_date),
                                               offset_id=offset_id,
                                               offset_peer=offset_peer,
                                               limit=count))

        return (r.dialogs,
                [self.find_display_name(d.peer, r.users, r.chats) for d in r.dialogs],
                [self.find_input_peer(d.peer, r.users, r.chats) for d in r.dialogs])

    def send_message(self, input_peer, message, markdown=False, no_web_page=False):
        """Sends a message to the given input peer"""
        if markdown:
            msg, entities = parse_message_entities(message)
        else:
            msg, entities = message, []

        self.invoke(SendMessageRequest(peer=input_peer,
                                       message=msg,
                                       random_id=utils.generate_random_long(),
                                       entities=entities,
                                       no_webpage=no_web_page))

    def get_message_history(self, input_peer, limit=20,
                            offset_date=None, offset_id=0, max_id=0, min_id=0, add_offset=0):
        """
        Gets the message history for the specified InputPeer

        :param input_peer:  The InputPeer from whom to retrieve the message history
        :param limit:       Number of messages to be retrieved
        :param offset_date: Offset date (messages *previous* to this date will be retrieved)
        :param offset_id:   Offset message ID (only messages *previous* to the given ID will be retrieved)
        :param max_id:      All the messages with a higher (newer) ID or equal to this will be excluded
        :param min_id:      All the messages with a lower (older) ID or equal to this will be excluded
        :param add_offset:  Additional message offset (all of the specified offsets + this offset = older messages)

        :return: A tuple containing total message count and two more lists ([messages], [senders]).
                 Note that the sender can be null if it was not found!
        """
        result = self.invoke(GetHistoryRequest(input_peer,
                                               limit=limit,
                                               offset_date=self.get_tg_date(offset_date),
                                               offset_id=offset_id,
                                               max_id=max_id,
                                               min_id=min_id,
                                               add_offset=add_offset))

        # The result may be a messages slice (not all messages were retrieved) or
        # simply a messages TLObject. In the later case, no "count" attribute is specified:
        # the total messages count is retrieved by counting all the retrieved messages
        total_messages = getattr(result, 'count', len(result.messages))
        
        return (total_messages,
                result.messages,
                [usr  # Create a list with the users...
                 if usr.id == msg.from_id else None  # ...whose ID equals the current message ID...
                 for msg in result.messages  # ...from all the messages...
                 for usr in result.users])  # ...from all of the available users

    def invoke(self, request):
        """Invokes an MTProtoRequest and returns its results"""
        if not issubclass(type(request), MTProtoRequest):
            raise ValueError('You can only invoke MtProtoRequests')

        self.sender.send(request)
        self.sender.receive(request)

        return request.result

    # endregion

    # region Utilities

    @staticmethod
    def get_tg_date(datetime):
        """Parses a datetime Python object to Telegram's required integer Unix timestamp"""
        return 0 if datetime is None else int(datetime.timestamp())

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
    def find_input_peer(peer, users, chats):
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

        # Only show incoming messages
        if type(tlobject) is UpdateShortMessage:
            if not tlobject.out:
                print('> User with ID {} said "{}"'.format(tlobject.user_id, tlobject.message))

    # endregion
