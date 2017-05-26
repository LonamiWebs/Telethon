import os
import pickle
import random
import time
from os.path import isfile as file_exists

from .. import helpers as utils


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
        self.user = None

    def save(self):
        """Saves the current session object as session_user_id.session"""
        if self.session_user_id:
            with open('{}.session'.format(self.session_user_id), 'wb') as file:
                pickle.dump(self, file)

    def delete(self):
        """Deletes the current session file"""
        try:
            os.remove('{}.session'.format(self.session_user_id))
            return True
        except OSError:
            return False

    @staticmethod
    def try_load_or_create_new(session_user_id):
        """Loads a saved session_user_id session, or creates a new one if none existed before.
           If the given session_user_id is None, we assume that it is for testing purposes"""
        if session_user_id is None:
            return Session(None)
        else:
            path = '{}.session'.format(session_user_id)

            if file_exists(path):
                with open(path, 'rb') as file:
                    return pickle.load(file)
            else:
                return Session(session_user_id)

    def get_new_msg_id(self):
        """Generates a new message ID based on the current time (in ms) since epoch"""
        # Refer to mtproto_plain_sender.py for the original method, this is a simple copy
        ms_time = int(time.time() * 1000)
        new_msg_id = (((ms_time // 1000 + self.time_offset) << 32)
                      |  # "must approximately equal unix time*2^32"
                      ((ms_time % 1000) << 22)
                      |  # "approximate moment in time the message was created"
                      random.randint(0, 524288)
                      << 2)  # "message identifiers are divisible by 4"

        if self.last_message_id >= new_msg_id:
            new_msg_id = self.last_message_id + 4

        self.last_message_id = new_msg_id
        return new_msg_id

    def update_time_offset(self, correct_msg_id):
        """Updates the time offset based on a known correct message ID"""
        now = int(time.time())
        correct = correct_msg_id >> 32
        self.time_offset = correct - now
