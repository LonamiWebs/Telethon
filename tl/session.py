# This file is based on TLSharp
# https://github.com/sochix/TLSharp/blob/master/TLSharp.Core/Session.cs
from os.path import isfile as file_exists
import time
import pickle
import utils.helpers as utils


class Session:
    def __init__(self, session_user_id):
        self.session_user_id = session_user_id
        self.server_address = '91.108.56.165'
        self.port = 443
        self.auth_key = None
        self.id = utils.generate_random_long(signed=False)
        self.sequence = 0
        self.salt = 0  # Unsigned long
        self.time_offset = 0
        self.last_message_id = 0  # Long
        self.session_expires = 0
        self.user = None

    def save(self):
        """Saves the current session object as session_user_id.session"""
        with open('{}.session'.format(self.session_user_id), 'wb') as file:
            pickle.dump(self, file)

    @staticmethod
    def try_load_or_create_new(self, session_user_id):
        """Loads a saved session_user_id session, or creates a new one if none existed before"""
        filepath = '{}.session'.format(self.session_user_id)

        if file_exists(filepath):
            with open(filepath, 'rb') as file:
                return pickle.load(self)
        else:
            return Session(session_user_id)

    def get_new_msg_id(self):
        """Generates a new message ID based on the current time (in ms) since epoch"""
        # Refer to mtproto_plain_sender.py for the original method, this is a simple copy
        new_msg_id = int(self.time_offset + time.time() * 1000)
        if self._last_msg_id >= new_msg_id:
            new_msg_id = self._last_msg_id + 4

        self._last_msg_id = new_msg_id
        return new_msg_id
