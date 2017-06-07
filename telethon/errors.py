import re


class ReadCancelledError(Exception):
    """Occurs when a read operation was cancelled"""

    def __init__(self):
        super().__init__(self, 'The read operation was cancelled.')


class InvalidParameterError(Exception):
    """Occurs when an invalid parameter is given, for example,
    when either A or B are required but none is given"""


class TypeNotFoundError(Exception):
    """Occurs when a type is not found, for example,
    when trying to read a TLObject with an invalid constructor code"""

    def __init__(self, invalid_constructor_id):
        super().__init__(
            self, 'Could not find a matching Constructor ID for the TLObject '
            'that was supposed to be read with ID {}. Most likely, a TLObject '
            'was trying to be read when it should not be read.'
            .format(hex(invalid_constructor_id)))

        self.invalid_constructor_id = invalid_constructor_id


class InvalidDCError(Exception):
    def __init__(self, rpc_error):
        self.new_dc = rpc_error.__dict__.pop('additional_data')
        self.__dict__.update(rpc_error.__dict__)


class InvalidChecksumError(Exception):
    def __init__(self, checksum, valid_checksum):
        super().__init__(
            self,
            'Invalid checksum ({} when {} was expected). This packet should be skipped.'
            .format(checksum, valid_checksum))

        self.checksum = checksum
        self.valid_checksum = valid_checksum


class FloodWaitError(Exception):
    def __init__(self, seconds):
        super().__init__(
            self,
            'Too many requests were made too fast. Must wait {} seconds.'
            .format(seconds)
        )
        self.seconds = seconds


class RPCError(Exception):

    CodeMessages = {
        303:
        ('ERROR_SEE_OTHER',
         'The request must be repeated, but directed to a different data center.'
         ),
        400:
        ('BAD_REQUEST',
         'The query contains errors. In the event that a request was created using a '
         'form and contains user generated data, the user should be notified that the '
         'data must be corrected before the query is repeated.'),
        401:
        ('UNAUTHORIZED',
         'There was an unauthorized attempt to use functionality available only to '
         'authorized users.'),
        403:
        ('FORBIDDEN',
         'Privacy violation. For example, an attempt to write a message to someone who '
         'has blacklisted the current user.'),
        404: ('NOT_FOUND',
              'An attempt to invoke a non-existent object, such as a method.'),
        420:
        ('FLOOD',
         'The maximum allowed number of attempts to invoke the given method with '
         'the given input parameters has been exceeded. For example, in an attempt '
         'to request a large number of text messages (SMS) for the same phone number.'
         ),
        500:
        ('INTERNAL',
         'An internal server error occurred while a request was being processed; '
         'for example, there was a disruption while accessing a database or file storage.'
         )
    }

    ErrorMessages = {
        # 303 ERROR_SEE_OTHER
        'FILE_MIGRATE_(\d+)':
        'The file to be accessed is currently stored in a different data center (#{}).',
        'PHONE_MIGRATE_(\d+)':
        'The phone number a user is trying to use for authorization is associated '
        'with a different data center (#{}).',
        'NETWORK_MIGRATE_(\d+)':
        'The source IP address is associated with a different data center (#{}, '
        'for registration).',
        'USER_MIGRATE_(\d+)':
        'The user whose identity is being used to execute queries is associated with '
        'a different data center  (#{} for registration).',

        # 400 BAD_REQUEST
        'FIRSTNAME_INVALID': 'The first name is invalid.',
        'LASTNAME_INVALID': 'The last name is invalid.',
        'PHONE_NUMBER_INVALID': 'The phone number is invalid.',
        'PHONE_CODE_HASH_EMPTY': 'The phone code hash is missing.',
        'PHONE_CODE_EMPTY': 'The phone code is missing.',
        'PHONE_CODE_INVALID': 'The phone code entered was invalid.',
        'PHONE_CODE_EXPIRED': 'The confirmation code has expired.',
        'PHONE_NUMBER_BANNED':
        'The used phone number has been banned from Telegram and cannot '
        'be used anymore. Possibly check https://www.telegram.org/faq_spam.',
        'API_ID_INVALID': 'The api_id/api_hash combination is invalid.',
        'PHONE_NUMBER_OCCUPIED': 'The phone number is already in use.',
        'PHONE_NUMBER_UNOCCUPIED': 'The phone number is not yet being used.',
        'USERS_TOO_FEW': 'Not enough users (to create a chat, for example).',
        'USERS_TOO_MUCH':
        'The maximum number of users has been exceeded (to create a chat, for example).',
        'TYPE_CONSTRUCTOR_INVALID': 'The type constructor is invalid.',
        'FILE_PART_INVALID': 'The file part number is invalid.',
        'FILE_PARTS_INVALID': 'The number of file parts is invalid.',
        'FILE_PART_(\d+)_MISSING':
        'Part {} of the file is missing from storage.',
        'MD5_CHECKSUM_INVALID': 'The MD5 check-sums do not match.',
        'PHOTO_INVALID_DIMENSIONS': 'The photo dimensions are invalid.',
        'FIELD_NAME_INVALID': 'The field with the name FIELD_NAME is invalid.',
        'FIELD_NAME_EMPTY': 'The field with the name FIELD_NAME is missing.',
        'MSG_WAIT_FAILED': 'A waiting call returned an error.',
        'CHAT_ADMIN_REQUIRED':
        'Chat admin privileges are required to do that in the specified chat '
        '(for example, to send a message in a channel which is not yours).',
        'PASSWORD_HASH_INVALID':
        'The password (and thus its hash value) you entered is invalid.',
        'BOT_METHOD_INVALID':
        'The API access for bot users is restricted. The method you tried '
        'to invoke cannot be executed as a bot.',
        'PEER_ID_INVALID':
        'An invalid Peer was used. Make sure to pass the right peer type.',
        'MESSAGE_EMPTY': 'Empty or invalid UTF-8 message was sent.',
        'MESSAGE_TOO_LONG':
        'Message was too long. Current maximum length is 4096 UTF-8 characters.',
        'USERNAME_INVALID':
        'Unacceptable username. Must match r"[a-zA-Z][\w\d]{4,32}"',
        'USERNAME_OCCUPIED': 'The username is already taken.',
        'USERNAME_NOT_OCCUPIED':
        'See issue #96 for Telethon - try upgrading the library.',
        'USERNAME_NOT_MODIFIED':
        'The username is not different from the current username',
        'USER_ID_INVALID':
        'Invalid object ID for an user. Make sure to pass the right types.',
        'CHAT_ID_INVALID':
        'Invalid object ID for a chat. Make sure to pass the right types.',
        'CHANNEL_INVALID':
        'Invalid channel object. Make sure to pass the right types.',
        'MESSAGE_ID_INVALID': 'The specified message ID is invalid.',
        'CONNECTION_LAYER_INVALID':
        'The very first request must always be InvokeWithLayerRequest.',
        'INPUT_METHOD_INVALID':
        'The invoked method does not exist anymore or has never existed.',
        'DC_ID_INVALID':
        'This occurs when an authorization is tried to be exported for '
        'the same data center one is currently connected to.',

        # 401 UNAUTHORIZED
        'AUTH_KEY_UNREGISTERED': 'The key is not registered in the system.',
        'AUTH_KEY_INVALID': 'The key is invalid.',
        'USER_DEACTIVATED': 'The user has been deleted/deactivated.',
        'SESSION_REVOKED':
        'The authorization has been invalidated, because of the user terminating all sessions.',
        'SESSION_EXPIRED': 'The authorization has expired.',
        'ACTIVE_USER_REQUIRED':
        'The method is only available to already activated users.',
        'AUTH_KEY_PERM_EMPTY':
        'The method is unavailable for temporary authorization key, not bound to permanent.',
        'SESSION_PASSWORD_NEEDED':
        'Two-steps verification is enabled and a password is required.',

        # 420 FLOOD
        'FLOOD_WAIT_(\d+)': 'A wait of {} seconds is required.'
    }

    def __init__(self, code, message):
        self.code = code
        self.code_meaning = RPCError.CodeMessages[code]

        self.message = message
        self.must_resend = code == 303  # ERROR_SEE_OTHER, "The request must be repeated"

        called_super = False
        for key, error_msg in RPCError.ErrorMessages.items():
            match = re.match(key, message)
            if match:
                error_msg = '{} ({}): {}'.format(
                    self.message, self.code, error_msg)

                # Get additional_data, if any
                if match.groups():
                    self.additional_data = int(match.group(1))
                    super().__init__(self,
                                     error_msg.format(self.additional_data))
                else:
                    self.additional_data = None
                    super().__init__(self, error_msg)

                    # Add another field to easily determine whether this error
                    # should be handled as a password-required error
                    self.password_required = message == 'SESSION_PASSWORD_NEEDED'

                called_super = True
                break

        if not called_super:
            super().__init__(
                self, 'Unknown error message with code {}: {}'.format(code,
                                                                      message))


class BadMessageError(Exception):
    """Occurs when handling a bad_message_notification"""
    ErrorMessages = {
        16:
        'msg_id too low (most likely, client time is wrong it would be worthwhile to '
        'synchronize it using msg_id notifications and re-send the original message '
        'with the "correct" msg_id or wrap it in a container with a new msg_id if the '
        'original message had waited too long on the client to be transmitted).',
        17:
        'msg_id too high (similar to the previous case, the client time has to be '
        'synchronized, and the message re-sent with the correct msg_id).',
        18:
        'Incorrect two lower order msg_id bits (the server expects client message msg_id '
        'to be divisible by 4).',
        19:
        'Container msg_id is the same as msg_id of a previously received message '
        '(this must never happen).',
        20:
        'Message too old, and it cannot be verified whether the server has received a '
        'message with this msg_id or not.',
        32:
        'msg_seqno too low (the server has already received a message with a lower '
        'msg_id but with either a higher or an equal and odd seqno).',
        33:
        'msg_seqno too high (similarly, there is a message with a higher msg_id but with '
        'either a lower or an equal and odd seqno).',
        34:
        'An even msg_seqno expected (irrelevant message), but odd received.',
        35: 'Odd msg_seqno expected (relevant message), but even received.',
        48:
        'Incorrect server salt (in this case, the bad_server_salt response is received with '
        'the correct salt, and the message is to be re-sent with it).',
        64: 'Invalid container.'
    }

    def __init__(self, code):
        super().__init__(self, BadMessageError.ErrorMessages.get(
            code,
            'Unknown error code (this should not happen): {}.'.format(code)))

        self.code = code
