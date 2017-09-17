import json
import os
import platform
import time
from threading import Lock
from base64 import b64encode, b64decode
from os.path import isfile as file_exists

from .. import helpers as utils


class Session:
    """This session contains the required information to login into your
       Telegram account. NEVER give the saved JSON file to anyone, since
       they would gain instant access to all your messages and contacts.

       If you think the session has been compromised, close all the sessions
       through an official Telegram client to revoke the authorization.
    """
    def __init__(self, session_user_id):
        """session_user_id should either be a string or another Session.
           Note that if another session is given, only parameters like
           those required to init a connection will be copied.
        """
        # These values will NOT be saved
        if isinstance(session_user_id, Session):
            self.session_user_id = None

            # For connection purposes
            session = session_user_id
            self.device_model = session.device_model
            self.system_version = session.system_version
            self.app_version = session.app_version
            self.lang_code = session.lang_code
            self.system_lang_code = session.system_lang_code
            self.lang_pack = session.lang_pack
            self.report_errors = session.report_errors

        else:  # str / None
            self.session_user_id = session_user_id

            system = platform.uname()
            self.device_model = system.system if system.system else 'Unknown'
            self.system_version = system.release if system.release else '1.0'
            self.app_version = '1.0'  # '0' will provoke error
            self.lang_code = 'en'
            self.system_lang_code = self.lang_code
            self.lang_pack = ''
            self.report_errors = True

        # Cross-thread safety
        self._lock = Lock()

        self.id = utils.generate_random_long(signed=False)
        self._sequence = 0
        self.time_offset = 0
        self._last_msg_id = 0  # Long

        # These values will be saved
        self.server_address = '91.108.56.165'
        self.port = 443
        self.auth_key = None
        self.layer = 0
        self.salt = 0  # Unsigned long

    def save(self):
        """Saves the current session object as session_user_id.session"""
        if self.session_user_id:
            with open('{}.session'.format(self.session_user_id), 'w') as file:
                json.dump({
                    'port': self.port,
                    'salt': self.salt,
                    'layer': self.layer,
                    'server_address': self.server_address,
                    'auth_key_data':
                        b64encode(self.auth_key.key).decode('ascii')
                        if self.auth_key else None
                }, file)

    def delete(self):
        """Deletes the current session file"""
        try:
            os.remove('{}.session'.format(self.session_user_id))
            return True
        except OSError:
            return False

    @staticmethod
    def list_sessions():
        """Lists all the sessions of the users who have ever connected
           using this client and never logged out
        """
        return [os.path.splitext(os.path.basename(f))[0]
                for f in os.listdir('.') if f.endswith('.session')]

    @staticmethod
    def try_load_or_create_new(session_user_id):
        """Loads a saved session_user_id.session or creates a new one.
           If session_user_id=None, later .save()'s will have no effect.
        """
        if session_user_id is None:
            return Session(None)
        else:
            path = '{}.session'.format(session_user_id)
            result = Session(session_user_id)
            if not file_exists(path):
                return result

            try:
                with open(path, 'r') as file:
                    data = json.load(file)
                    result.port = data.get('port', result.port)
                    result.salt = data.get('salt', result.salt)
                    result.layer = data.get('layer', result.layer)
                    result.server_address = \
                        data.get('server_address', result.server_address)

                    # FIXME We need to import the AuthKey here or otherwise
                    # we get cyclic dependencies.
                    from ..crypto import AuthKey
                    if data['auth_key_data'] is not None:
                        key = b64decode(data['auth_key_data'])
                        result.auth_key = AuthKey(data=key)

            except (json.decoder.JSONDecodeError, UnicodeDecodeError):
                pass

            return result

    def generate_sequence(self, content_related):
        """Thread safe method to generates the next sequence number,
           based on whether it was confirmed yet or not.

           Note that if confirmed=True, the sequence number
           will be increased by one too
        """
        with self._lock:
            if content_related:
                result = self._sequence * 2 + 1
                self._sequence += 1
                return result
            else:
                return self._sequence * 2

    def get_new_msg_id(self):
        """Generates a new unique message ID based on the current
           time (in ms) since epoch"""
        # Refer to mtproto_plain_sender.py for the original method
        now = time.time()
        nanoseconds = int((now - int(now)) * 1e+9)
        # "message identifiers are divisible by 4"
        new_msg_id = (int(now) << 32) | (nanoseconds << 2)

        with self._lock:
            if self._last_msg_id >= new_msg_id:
                new_msg_id = self._last_msg_id + 4

            self._last_msg_id = new_msg_id

        return new_msg_id

    def update_time_offset(self, correct_msg_id):
        """Updates the time offset based on a known correct message ID"""
        now = int(time.time())
        correct = correct_msg_id >> 32
        self.time_offset = correct - now
