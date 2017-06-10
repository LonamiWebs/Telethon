from . import BadRequestError


class ApiIdInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__(
            self,
            'The api_id/api_hash combination is invalid.'
        )


class BotMethodInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__(
            self,
            'The API access for bot users is restricted. The method you '
            'tried to invoke cannot be executed as a bot.'
        )


class ChannelInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__(
            self,
            'Invalid channel object. Make sure to pass the right types.'
        )


class ChatAdminRequiredError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__(
            self,
            'Chat admin privileges are required to do that in the specified '
            'chat (for example, to send a message in a channel which is not '
            'yours).'
        )


class ChatIdInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__(
            self,
            'Invalid object ID for a chat. Make sure to pass the right types.'
        )


class ConnectionLayerInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__(
            self,
            'The very first request must always be InvokeWithLayerRequest.'
        )


class DcIdInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__(
            self,
            'This occurs when an authorization is tried to be exported for '
            'the same data center one is currently connected to.'
        )


class FieldNameEmptyError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__(
            self,
            'The field with the name FIELD_NAME is missing.'
        )


class FieldNameInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__(
            self,
            'The field with the name FIELD_NAME is invalid.'
        )


class FilePartsInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__(
            self,
            'The number of file parts is invalid.'
        )


class FilePartMissingError(BadRequestError):
    def __init__(self, **kwargs):
        self.which = kwargs['extra']
        super(Exception, self).__init__(
            self,
            'Part {} of the file is missing from storage.'.format(self.which)
        )


class FilePartInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__(
            self,
            'The file part number is invalid.'
        )


class FirstNameInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__(
            self,
            'The first name is invalid.'
        )


class InputMethodInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__(
            self,
            'The invoked method does not exist anymore or has never existed.'
        )


class LastNameInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__(
            self,
            'The last name is invalid.'
        )


class Md5ChecksumInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__(
            self,
            'The MD5 check-sums do not match.'
        )


class MessageEmptyError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__(
            self,
            'Empty or invalid UTF-8 message was sent.'
        )


class MessageIdInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__(
            self,
            'The specified message ID is invalid.'
        )


class MessageTooLongError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__(
            self,
            'Message was too long. Current maximum length is 4096 UTF-8 '
            'characters.'
        )


class MsgWaitFailedError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__(
            self,
            'A waiting call returned an error.'
        )


class PasswordHashInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__(
            self,
            'The password (and thus its hash value) you entered is invalid.'
        )


class PeerIdInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__(
            self,
            'An invalid Peer was used. Make sure to pass the right peer type.'
        )


class PhoneCodeEmptyError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__(
            self,
            'The phone code is missing.'
        )


class PhoneCodeExpiredError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__(
            self,
            'The confirmation code has expired.'
        )


class PhoneCodeHashEmptyError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__(
            self,
            'The phone code hash is missing.'
        )


class PhoneCodeInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__(
            self,
            'The phone code entered was invalid.'
        )


class PhoneNumberBannedError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__(
            self,
            'The used phone number has been banned from Telegram and cannot '
            'be used anymore. Maybe check https://www.telegram.org/faq_spam.'
        )


class PhoneNumberInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__(
            self,
            'The phone number is invalid.'
        )


class PhoneNumberOccupiedError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__(
            self,
            'The phone number is already in use.'
        )


class PhoneNumberUnoccupiedError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__(
            self,
            'The phone number is not yet being used.'
        )


class PhotoInvalidDimensionsError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__(
            self,
            'The photo dimensions are invalid.'
        )


class TypeConstructorInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__(
            self,
            'The type constructor is invalid.'
        )


class UsernameInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__(
            self,
            'Unacceptable username. Must match r"[a-zA-Z][\w\d]{4,32}"'
        )


class UsernameNotModifiedError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__(
            self,
            'The username is not different from the current username'
        )


class UsernameNotOccupiedError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__(
            self,
            'See issue #96 for Telethon - try upgrading the library.'
        )


class UsernameOccupiedError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__(
            self,
            'The username is already taken.'
        )


class UsersTooFewError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__(
            self,
            'Not enough users (to create a chat, for example).'
        )


class UsersTooMuchError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__(
            self,
            'The maximum number of users has been exceeded (to create a '
            'chat, for example).'
        )


class UserIdInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__(
            self,
            'Invalid object ID for an user. Make sure to pass the right types.'
        )


rpc_400_errors = {
    'API_ID_INVALID': ApiIdInvalidError,
    'BOT_METHOD_INVALID': BotMethodInvalidError,
    'CHANNEL_INVALID': ChannelInvalidError,
    'CHAT_ADMIN_REQUIRED': ChatAdminRequiredError,
    'CHAT_ID_INVALID': ChatIdInvalidError,
    'CONNECTION_LAYER_INVALID': ConnectionLayerInvalidError,
    'DC_ID_INVALID': DcIdInvalidError,
    'FIELD_NAME_EMPTY': FieldNameEmptyError,
    'FIELD_NAME_INVALID': FieldNameInvalidError,
    'FILE_PARTS_INVALID': FilePartsInvalidError,
    'FILE_PART_(\d+)_MISSING': FilePartMissingError,
    'FILE_PART_INVALID': FilePartInvalidError,
    'FIRSTNAME_INVALID': FirstNameInvalidError,
    'INPUT_METHOD_INVALID': InputMethodInvalidError,
    'LASTNAME_INVALID': LastNameInvalidError,
    'MD5_CHECKSUM_INVALID': Md5ChecksumInvalidError,
    'MESSAGE_EMPTY': MessageEmptyError,
    'MESSAGE_ID_INVALID': MessageIdInvalidError,
    'MESSAGE_TOO_LONG': MessageTooLongError,
    'MSG_WAIT_FAILED': MsgWaitFailedError,
    'PASSWORD_HASH_INVALID': PasswordHashInvalidError,
    'PEER_ID_INVALID': PeerIdInvalidError,
    'PHONE_CODE_EMPTY': PhoneCodeEmptyError,
    'PHONE_CODE_EXPIRED': PhoneCodeExpiredError,
    'PHONE_CODE_HASH_EMPTY': PhoneCodeHashEmptyError,
    'PHONE_CODE_INVALID': PhoneCodeInvalidError,
    'PHONE_NUMBER_BANNED': PhoneNumberBannedError,
    'PHONE_NUMBER_INVALID': PhoneNumberInvalidError,
    'PHONE_NUMBER_OCCUPIED': PhoneNumberOccupiedError,
    'PHONE_NUMBER_UNOCCUPIED': PhoneNumberUnoccupiedError,
    'PHOTO_INVALID_DIMENSIONS': PhotoInvalidDimensionsError,
    'TYPE_CONSTRUCTOR_INVALID': TypeConstructorInvalidError,
    'USERNAME_INVALID': UsernameInvalidError,
    'USERNAME_NOT_MODIFIED': UsernameNotModifiedError,
    'USERNAME_NOT_OCCUPIED': UsernameNotOccupiedError,
    'USERNAME_OCCUPIED': UsernameOccupiedError,
    'USERS_TOO_FEW': UsersTooFewError,
    'USERS_TOO_MUCH': UsersTooMuchError,
    'USER_ID_INVALID': UserIdInvalidError,
}
