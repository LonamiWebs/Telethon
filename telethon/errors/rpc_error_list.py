from .rpc_base_errors import RPCError, BadMessageError, InvalidDCError, BadRequestError, UnauthorizedError, ForbiddenError, NotFoundError, FloodError, ServerError


class RPCErrorNeg503(RPCError):
    code = -503


class FloodTestPhoneWaitError(FloodError):
    def __init__(self, **kwargs):
        self.seconds = int(kwargs.get('capture', 0))
        super(Exception, self).__init__('A wait of {} seconds is required in the test servers'.format(self.seconds))


class FloodWaitError(FloodError):
    def __init__(self, **kwargs):
        self.seconds = int(kwargs.get('capture', 0))
        super(Exception, self).__init__('A wait of {} seconds is required'.format(self.seconds))


class ActiveUserRequiredError(UnauthorizedError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The method is only available to already activated users')


class AuthKeyInvalidError(UnauthorizedError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The key is invalid')


class AuthKeyPermEmptyError(UnauthorizedError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The method is unavailable for temporary authorization key, not bound to permanent')


class AuthKeyUnregisteredError(UnauthorizedError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The key is not registered in the system')


class SessionExpiredError(UnauthorizedError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The authorization has expired')


class SessionPasswordNeededError(UnauthorizedError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('Two-steps verification is enabled and a password is required')


class SessionRevokedError(UnauthorizedError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The authorization has been invalidated, because of the user terminating all sessions')


class UserDeactivatedError(UnauthorizedError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The user has been deleted/deactivated')


class FileMigrateError(InvalidDCError):
    def __init__(self, **kwargs):
        self.new_dc = int(kwargs.get('capture', 0))
        super(Exception, self).__init__('The file to be accessed is currently stored in DC {}'.format(self.new_dc))


class NetworkMigrateError(InvalidDCError):
    def __init__(self, **kwargs):
        self.new_dc = int(kwargs.get('capture', 0))
        super(Exception, self).__init__('The source IP address is associated with DC {}'.format(self.new_dc))


class PhoneMigrateError(InvalidDCError):
    def __init__(self, **kwargs):
        self.new_dc = int(kwargs.get('capture', 0))
        super(Exception, self).__init__('The phone number a user is trying to use for authorization is associated with DC {}'.format(self.new_dc))


class UserMigrateError(InvalidDCError):
    def __init__(self, **kwargs):
        self.new_dc = int(kwargs.get('capture', 0))
        super(Exception, self).__init__('The user whose identity is being used to execute queries is associated with DC {}'.format(self.new_dc))


class TimeoutError(RPCErrorNeg503):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('No description known.')


class AboutTooLongError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The provided bio is too long')


class AccessTokenExpiredError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('Bot token expired')


class AccessTokenInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The provided token is not valid')


class AdminsTooMuchError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('Too many admins')


class ApiIdInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The api_id/api_hash combination is invalid')


class ApiIdPublishedFloodError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__("This API id was published somewhere, you can't use it now")


class ArticleTitleEmptyError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The title of the article is empty')


class AuthBytesInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The provided authorization is invalid')


class BotsTooMuchError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('There are too many bots in this chat/channel')


class BotChannelsNaError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__("Bots can't edit admin privileges")


class BotGroupsBlockedError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__("This bot can't be added to groups")


class BotInlineDisabledError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__("This bot can't be used in inline mode")


class BotInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('This is not a valid bot')


class BotMethodInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The API access for bot users is restricted. The method you tried to invoke cannot be executed as a bot')


class BotMissingError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('This method can only be run by a bot')


class ButtonDataInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The provided button data is invalid')


class ButtonTypeInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The type of one of the buttons you provided is invalid')


class ButtonUrlInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('Button URL invalid')


class CallAlreadyAcceptedError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The call was already accepted')


class CallAlreadyDeclinedError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The call was already declined')


class CallPeerInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The provided call peer object is invalid')


class CallProtocolFlagsInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('Call protocol flags invalid')


class CdnMethodInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('This method cannot be invoked on a CDN server. Refer to https://core.telegram.org/cdn#schema for available methods')


class ChannelsAdminPublicTooMuchError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__("You're admin of too many public channels, make some channels private to change the username of this channel")


class ChannelsTooMuchError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('You have joined too many channels/supergroups')


class ChannelInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('Invalid channel object. Make sure to pass the right types, for instance making sure that the request is designed for channels or otherwise look for a different one more suited')


class ChannelPrivateError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The channel specified is private and you lack permission to access it. Another reason may be that you were banned from it')


class ChatAboutNotModifiedError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('About text has not changed')


class ChatAboutTooLongError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('Chat about too long')


class ChatAdminRequiredError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('Chat admin privileges are required to do that in the specified chat (for example, to send a message in a channel which is not yours)')


class ChatForbiddenError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('You cannot write in this chat')


class ChatIdEmptyError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The provided chat ID is empty')


class ChatIdInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('Invalid object ID for a chat. Make sure to pass the right types, for instance making sure that the request is designed for chats (not channels/megagroups) or otherwise look for a different one more suited\\nAn example working with a megagroup and AddChatUserRequest, it will fail because megagroups are channels. Use InviteToChannelRequest instead')


class ChatNotModifiedError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__("The pinned message wasn't modified")


class ChatTitleEmptyError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('No chat title provided')


class CodeEmptyError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The provided code is empty')


class CodeHashInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('Code hash invalid')


class ConnectionApiIdInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The provided API id is invalid')


class ConnectionDeviceModelEmptyError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('Device model empty')


class ConnectionLangPackInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The specified language pack is not valid. This is meant to be used by official applications only so far, leave it empty')


class ConnectionLayerInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The very first request must always be InvokeWithLayerRequest')


class ConnectionNotInitedError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('Connection not initialized')


class ConnectionSystemEmptyError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('Connection system empty')


class ContactIdInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The provided contact ID is invalid')


class DataInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('Encrypted data invalid')


class DataJsonInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The provided JSON data is invalid')


class DateEmptyError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('Date empty')


class DcIdInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('This occurs when an authorization is tried to be exported for the same data center one is currently connected to')


class DhGAInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('g_a invalid')


class EmailUnconfirmedError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('Email unconfirmed')


class EncryptedMessageInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('Encrypted message invalid')


class EncryptionAlreadyAcceptedError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('Secret chat already accepted')


class EncryptionAlreadyDeclinedError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The secret chat was already declined')


class EncryptionDeclinedError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The secret chat was declined')


class EncryptionIdInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The provided secret chat ID is invalid')


class EntityMentionUserInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__("You can't use this entity")


class ErrorTextEmptyError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The provided error message is empty')


class ExportCardInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('Provided card is invalid')


class ExternalUrlInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('External URL invalid')


class FieldNameEmptyError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The field with the name FIELD_NAME is missing')


class FieldNameInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The field with the name FIELD_NAME is invalid')


class FileIdInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The provided file id is invalid')


class FilePartsInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The number of file parts is invalid')


class FilePartEmptyError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The provided file part is empty')


class FilePartInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The file part number is invalid')


class FilePartLengthInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The length of a file part is invalid')


class FilePartSizeInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The provided file part size is invalid')


class FilePartMissingError(BadRequestError):
    def __init__(self, **kwargs):
        self.which = int(kwargs.get('capture', 0))
        super(Exception, self).__init__('Part {} of the file is missing from storage'.format(self.which))


class FirstNameInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The first name is invalid')


class GifIdInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The provided GIF ID is invalid')


class GroupedMediaInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('Invalid grouped media')


class HashInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The provided hash is invalid')


class ImageProcessFailedError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('Failure while processing image')


class InlineResultExpiredError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The inline query expired')


class InputConstructorInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The provided constructor is invalid')


class InputFetchErrorError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('An error occurred while deserializing TL parameters')


class InputFetchFailError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('Failed deserializing TL payload')


class InputLayerInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The provided layer is invalid')


class InputMethodInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The invoked method does not exist anymore or has never existed')


class InputRequestTooLongError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The input request was too long. This may be a bug in the library as it can occur when serializing more bytes than it should (likeappending the vector constructor code at the end of a message)')


class InputUserDeactivatedError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The specified user was deleted')


class InterdcCallErrorError(BadRequestError):
    def __init__(self, **kwargs):
        self.x = int(kwargs.get('capture', 0))
        super(Exception, self).__init__('No description known.'.format(self.x))


class InterdcCallRichErrorError(BadRequestError):
    def __init__(self, **kwargs):
        self.x = int(kwargs.get('capture', 0))
        super(Exception, self).__init__('No description known.'.format(self.x))


class InviteHashEmptyError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The invite hash is empty')


class InviteHashExpiredError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The chat the user tried to join has expired and is not valid anymore')


class InviteHashInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The invite hash is invalid')


class LangPackInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The provided language pack is invalid')


class LastnameInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The last name is invalid')


class LimitInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('An invalid limit was provided. See https://core.telegram.org/api/files#downloading-files')


class LocationInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The location given for a file was invalid. See https://core.telegram.org/api/files#downloading-files')


class MaxIdInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The provided max ID is invalid')


class Md5ChecksumInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The MD5 check-sums do not match')


class MediaCaptionTooLongError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The caption is too long')


class MediaEmptyError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The provided media object is invalid')


class MediaInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('Media invalid')


class MessageEditTimeExpiredError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__("You can't edit this message anymore, too much time has passed since its creation.")


class MessageEmptyError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('Empty or invalid UTF-8 message was sent')


class MessageIdsEmptyError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('No message ids were provided')


class MessageIdInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The specified message ID is invalid')


class MessageNotModifiedError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('Content of the message was not modified')


class MessageTooLongError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('Message was too long. Current maximum length is 4096 UTF-8 characters')


class MsgWaitFailedError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('A waiting call returned an error')


class NewSaltInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The new salt is invalid')


class NewSettingsInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The new settings are invalid')


class OffsetInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The given offset was invalid, it must be divisible by 1KB. See https://core.telegram.org/api/files#downloading-files')


class OffsetPeerIdInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The provided offset peer is invalid')


class PackShortNameInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('Short pack name invalid')


class PackShortNameOccupiedError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('A stickerpack with this name already exists')


class ParticipantsTooFewError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('Not enough participants')


class ParticipantVersionOutdatedError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The other participant does not use an up to date telegram client with support for calls')


class PasswordEmptyError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The provided password is empty')


class PasswordHashInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The password (and thus its hash value) you entered is invalid')


class PeerFloodError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('Too many requests')


class PeerIdInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('An invalid Peer was used. Make sure to pass the right peer type')


class PeerIdNotSupportedError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The provided peer ID is not supported')


class PersistentTimestampEmptyError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('Persistent timestamp empty')


class PersistentTimestampInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('Persistent timestamp invalid')


class PhoneCodeEmptyError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The phone code is missing')


class PhoneCodeExpiredError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The confirmation code has expired')


class PhoneCodeHashEmptyError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The phone code hash is missing')


class PhoneCodeInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The phone code entered was invalid')


class PhoneNumberAppSignupForbiddenError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('')


class PhoneNumberBannedError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The used phone number has been banned from Telegram and cannot be used anymore. Maybe check https://www.telegram.org/faq_spam')


class PhoneNumberFloodError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('You asked for the code too many times.')


class PhoneNumberInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The phone number is invalid')


class PhoneNumberOccupiedError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The phone number is already in use')


class PhoneNumberUnoccupiedError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The phone number is not yet being used')


class PhonePasswordFloodError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('You have tried logging in too many times')


class PhonePasswordProtectedError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('This phone is password protected')


class PhotoCropSizeSmallError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('Photo is too small')


class PhotoExtInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The extension of the photo is invalid')


class PhotoInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('Photo invalid')


class PhotoInvalidDimensionsError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The photo dimensions are invalid')


class PrivacyKeyInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The privacy key is invalid')


class QueryIdEmptyError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The query ID is empty')


class QueryIdInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The query ID is invalid')


class QueryTooShortError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The query string is too short')


class RandomIdInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('A provided random ID is invalid')


class RandomLengthInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('Random length invalid')


class RangesInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('Invalid range provided')


class ReplyMarkupInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The provided reply markup is invalid')


class ResultTypeInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('Result type invalid')


class RpcCallFailError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('Telegram is having internal issues, please try again later.')


class RpcMcgetFailError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('Telegram is having internal issues, please try again later.')


class RsaDecryptFailedError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('Internal RSA decryption failed')


class SearchQueryEmptyError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The search query is empty')


class SendMessageTypeInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The message type is invalid')


class Sha256HashInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The provided SHA256 hash is invalid')


class StartParamEmptyError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The start parameter is empty')


class StartParamInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('Start parameter invalid')


class StickersetInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The provided sticker set is invalid')


class StickersEmptyError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('No sticker provided')


class StickerEmojiInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('Sticker emoji invalid')


class StickerFileInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('Sticker file invalid')


class StickerIdInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The provided sticker ID is invalid')


class StickerInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The provided sticker is invalid')


class StickerPngDimensionsError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('Sticker png dimensions invalid')


class TempAuthKeyEmptyError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('No temporary auth key provided')


class TmpPasswordDisabledError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The temporary password is disabled')


class TokenInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The provided token is invalid')


class TtlDaysInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The provided TTL is invalid')


class TypesEmptyError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The types field is empty')


class TypeConstructorInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The type constructor is invalid')


class UsernameInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('Nobody is using this username, or the username is unacceptable. If the latter, it must match r"[a-zA-Z][\\w\\d]{3,30}[a-zA-Z\\d]"')


class UsernameNotModifiedError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The username is not different from the current username')


class UsernameNotOccupiedError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The username is not in use by anyone else yet')


class UsernameOccupiedError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The username is already taken')


class UsersTooFewError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('Not enough users (to create a chat, for example)')


class UsersTooMuchError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The maximum number of users has been exceeded (to create a chat, for example)')


class UserAdminInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__("You're not an admin")


class UserAlreadyParticipantError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The authenticated user is already a participant of the chat')


class UserBannedInChannelError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__("You're banned from sending messages in supergroups/channels")


class UserBlockedError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('User blocked')


class UserBotError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('Bots can only be admins in channels.')


class UserBotInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('This method can only be called by a bot')


class UserBotRequiredError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('This method can only be called by a bot')


class UserCreatorError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__("You can't leave this channel, because you're its creator")


class UserIdInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('Invalid object ID for an user. Make sure to pass the right types, for instance making sure that the request is designed for users or otherwise look for a different one more suited')


class UserIsBlockedError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('User is blocked')


class UserIsBotError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__("Bots can't send messages to other bots")


class UserKickedError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('This user was kicked from this supergroup/channel')


class UserNotMutualContactError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The provided user is not a mutual contact')


class UserNotParticipantError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__("You're not a member of this supergroup/channel")


class WcConvertUrlInvalidError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('WC convert URL invalid')


class WebpageCurlFailedError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('Failure while fetching the webpage with cURL')


class WebpageMediaEmptyError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('Webpage media empty')


class YouBlockedUserError(BadRequestError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('You blocked this user')


class ChannelPublicGroupNaError(ForbiddenError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('channel/supergroup not available')


class ChatAdminInviteRequiredError(ForbiddenError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('You do not have the rights to do this')


class ChatAdminRequiredError(ForbiddenError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('Chat admin privileges are required to do that in the specified chat (for example, to send a message in a channel which is not yours)')


class ChatSendGifsForbiddenError(ForbiddenError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__("You can't send gifs in this chat")


class ChatSendMediaForbiddenError(ForbiddenError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__("You can't send media in this chat")


class ChatSendStickersForbiddenError(ForbiddenError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__("You can't send stickers in this chat.")


class ChatWriteForbiddenError(ForbiddenError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__("You can't write in this chat")


class MessageAuthorRequiredError(ForbiddenError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('Message author required')


class MessageDeleteForbiddenError(ForbiddenError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__("You can't delete one of the messages you tried to delete, most likely because it is a service message.")


class RightForbiddenError(ForbiddenError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('Your admin rights do not allow you to do this')


class UserBotInvalidError(ForbiddenError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('This method can only be called by a bot')


class UserChannelsTooMuchError(ForbiddenError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('One of the users you tried to add is already in too many channels/supergroups')


class UserIsBlockedError(ForbiddenError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('User is blocked')


class UserNotMutualContactError(ForbiddenError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The provided user is not a mutual contact')


class UserPrivacyRestrictedError(ForbiddenError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__("The user's privacy settings do not allow you to do this")


class UserRestrictedError(ForbiddenError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__("You're spamreported, you can't create channels or chats.")


class AuthRestartError(ServerError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('Restart the authorization process')


class CallOccupyFailedError(ServerError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The call failed because the user is already making another call')


class EncryptionOccupyFailedError(ServerError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('Internal server error while accepting secret chat')


class HistoryGetFailedError(ServerError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('Fetching of history failed')


class MemberNoLocationError(ServerError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__("An internal failure occurred while fetching user info (couldn't find location)")


class MemberOccupyPrimaryLocFailedError(ServerError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('Occupation of primary member location failed')


class NeedChatInvalidError(ServerError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The provided chat is invalid')


class NeedMemberInvalidError(ServerError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The provided member is invalid')


class ParticipantCallFailedError(ServerError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('Failure while making call')


class PersistentTimestampOutdatedError(ServerError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('Persistent timestamp outdated')


class PtsChangeEmptyError(ServerError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('No PTS change')


class RandomIdDuplicateError(ServerError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('You provided a random ID that was already used')


class RegIdGenerateFailedError(ServerError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('Failure while generating registration ID')


class StorageCheckFailedError(ServerError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('Server storage check failed')


class StoreInvalidScalarTypeError(ServerError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('')


class UnknownMethodError(ServerError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__('The method you tried to call cannot be called on non-CDN DCs')


rpc_errors_all = {
    'FLOOD_TEST_PHONE_WAIT_(\\d+)': FloodTestPhoneWaitError,
    'FLOOD_WAIT_(\\d+)': FloodWaitError,
    'ACTIVE_USER_REQUIRED': ActiveUserRequiredError,
    'AUTH_KEY_INVALID': AuthKeyInvalidError,
    'AUTH_KEY_PERM_EMPTY': AuthKeyPermEmptyError,
    'AUTH_KEY_UNREGISTERED': AuthKeyUnregisteredError,
    'SESSION_EXPIRED': SessionExpiredError,
    'SESSION_PASSWORD_NEEDED': SessionPasswordNeededError,
    'SESSION_REVOKED': SessionRevokedError,
    'USER_DEACTIVATED': UserDeactivatedError,
    'FILE_MIGRATE_(\\d+)': FileMigrateError,
    'NETWORK_MIGRATE_(\\d+)': NetworkMigrateError,
    'PHONE_MIGRATE_(\\d+)': PhoneMigrateError,
    'USER_MIGRATE_(\\d+)': UserMigrateError,
    'TIMEOUT': TimeoutError,
    'ABOUT_TOO_LONG': AboutTooLongError,
    'ACCESS_TOKEN_EXPIRED': AccessTokenExpiredError,
    'ACCESS_TOKEN_INVALID': AccessTokenInvalidError,
    'ADMINS_TOO_MUCH': AdminsTooMuchError,
    'API_ID_INVALID': ApiIdInvalidError,
    'API_ID_PUBLISHED_FLOOD': ApiIdPublishedFloodError,
    'ARTICLE_TITLE_EMPTY': ArticleTitleEmptyError,
    'AUTH_BYTES_INVALID': AuthBytesInvalidError,
    'BOTS_TOO_MUCH': BotsTooMuchError,
    'BOT_CHANNELS_NA': BotChannelsNaError,
    'BOT_GROUPS_BLOCKED': BotGroupsBlockedError,
    'BOT_INLINE_DISABLED': BotInlineDisabledError,
    'BOT_INVALID': BotInvalidError,
    'BOT_METHOD_INVALID': BotMethodInvalidError,
    'BOT_MISSING': BotMissingError,
    'BUTTON_DATA_INVALID': ButtonDataInvalidError,
    'BUTTON_TYPE_INVALID': ButtonTypeInvalidError,
    'BUTTON_URL_INVALID': ButtonUrlInvalidError,
    'CALL_ALREADY_ACCEPTED': CallAlreadyAcceptedError,
    'CALL_ALREADY_DECLINED': CallAlreadyDeclinedError,
    'CALL_PEER_INVALID': CallPeerInvalidError,
    'CALL_PROTOCOL_FLAGS_INVALID': CallProtocolFlagsInvalidError,
    'CDN_METHOD_INVALID': CdnMethodInvalidError,
    'CHANNELS_ADMIN_PUBLIC_TOO_MUCH': ChannelsAdminPublicTooMuchError,
    'CHANNELS_TOO_MUCH': ChannelsTooMuchError,
    'CHANNEL_INVALID': ChannelInvalidError,
    'CHANNEL_PRIVATE': ChannelPrivateError,
    'CHAT_ABOUT_NOT_MODIFIED': ChatAboutNotModifiedError,
    'CHAT_ABOUT_TOO_LONG': ChatAboutTooLongError,
    'CHAT_ADMIN_REQUIRED': ChatAdminRequiredError,
    'CHAT_FORBIDDEN': ChatForbiddenError,
    'CHAT_ID_EMPTY': ChatIdEmptyError,
    'CHAT_ID_INVALID': ChatIdInvalidError,
    'CHAT_NOT_MODIFIED': ChatNotModifiedError,
    'CHAT_TITLE_EMPTY': ChatTitleEmptyError,
    'CODE_EMPTY': CodeEmptyError,
    'CODE_HASH_INVALID': CodeHashInvalidError,
    'CONNECTION_API_ID_INVALID': ConnectionApiIdInvalidError,
    'CONNECTION_DEVICE_MODEL_EMPTY': ConnectionDeviceModelEmptyError,
    'CONNECTION_LANG_PACK_INVALID': ConnectionLangPackInvalidError,
    'CONNECTION_LAYER_INVALID': ConnectionLayerInvalidError,
    'CONNECTION_NOT_INITED': ConnectionNotInitedError,
    'CONNECTION_SYSTEM_EMPTY': ConnectionSystemEmptyError,
    'CONTACT_ID_INVALID': ContactIdInvalidError,
    'DATA_INVALID': DataInvalidError,
    'DATA_JSON_INVALID': DataJsonInvalidError,
    'DATE_EMPTY': DateEmptyError,
    'DC_ID_INVALID': DcIdInvalidError,
    'DH_G_A_INVALID': DhGAInvalidError,
    'EMAIL_UNCONFIRMED': EmailUnconfirmedError,
    'ENCRYPTED_MESSAGE_INVALID': EncryptedMessageInvalidError,
    'ENCRYPTION_ALREADY_ACCEPTED': EncryptionAlreadyAcceptedError,
    'ENCRYPTION_ALREADY_DECLINED': EncryptionAlreadyDeclinedError,
    'ENCRYPTION_DECLINED': EncryptionDeclinedError,
    'ENCRYPTION_ID_INVALID': EncryptionIdInvalidError,
    'ENTITY_MENTION_USER_INVALID': EntityMentionUserInvalidError,
    'ERROR_TEXT_EMPTY': ErrorTextEmptyError,
    'EXPORT_CARD_INVALID': ExportCardInvalidError,
    'EXTERNAL_URL_INVALID': ExternalUrlInvalidError,
    'FIELD_NAME_EMPTY': FieldNameEmptyError,
    'FIELD_NAME_INVALID': FieldNameInvalidError,
    'FILE_ID_INVALID': FileIdInvalidError,
    'FILE_PARTS_INVALID': FilePartsInvalidError,
    'FILE_PART_EMPTY': FilePartEmptyError,
    'FILE_PART_INVALID': FilePartInvalidError,
    'FILE_PART_LENGTH_INVALID': FilePartLengthInvalidError,
    'FILE_PART_SIZE_INVALID': FilePartSizeInvalidError,
    'FILE_PART_(\\d+)_MISSING': FilePartMissingError,
    'FIRSTNAME_INVALID': FirstNameInvalidError,
    'GIF_ID_INVALID': GifIdInvalidError,
    'GROUPED_MEDIA_INVALID': GroupedMediaInvalidError,
    'HASH_INVALID': HashInvalidError,
    'IMAGE_PROCESS_FAILED': ImageProcessFailedError,
    'INLINE_RESULT_EXPIRED': InlineResultExpiredError,
    'INPUT_CONSTRUCTOR_INVALID': InputConstructorInvalidError,
    'INPUT_FETCH_ERROR': InputFetchErrorError,
    'INPUT_FETCH_FAIL': InputFetchFailError,
    'INPUT_LAYER_INVALID': InputLayerInvalidError,
    'INPUT_METHOD_INVALID': InputMethodInvalidError,
    'INPUT_REQUEST_TOO_LONG': InputRequestTooLongError,
    'INPUT_USER_DEACTIVATED': InputUserDeactivatedError,
    'INTERDC_(\\d+)_CALL_ERROR': InterdcCallErrorError,
    'INTERDC_(\\d+)_CALL_RICH_ERROR': InterdcCallRichErrorError,
    'INVITE_HASH_EMPTY': InviteHashEmptyError,
    'INVITE_HASH_EXPIRED': InviteHashExpiredError,
    'INVITE_HASH_INVALID': InviteHashInvalidError,
    'LANG_PACK_INVALID': LangPackInvalidError,
    'LASTNAME_INVALID': LastnameInvalidError,
    'LIMIT_INVALID': LimitInvalidError,
    'LOCATION_INVALID': LocationInvalidError,
    'MAX_ID_INVALID': MaxIdInvalidError,
    'MD5_CHECKSUM_INVALID': Md5ChecksumInvalidError,
    'MEDIA_CAPTION_TOO_LONG': MediaCaptionTooLongError,
    'MEDIA_EMPTY': MediaEmptyError,
    'MEDIA_INVALID': MediaInvalidError,
    'MESSAGE_EDIT_TIME_EXPIRED': MessageEditTimeExpiredError,
    'MESSAGE_EMPTY': MessageEmptyError,
    'MESSAGE_IDS_EMPTY': MessageIdsEmptyError,
    'MESSAGE_ID_INVALID': MessageIdInvalidError,
    'MESSAGE_NOT_MODIFIED': MessageNotModifiedError,
    'MESSAGE_TOO_LONG': MessageTooLongError,
    'MSG_WAIT_FAILED': MsgWaitFailedError,
    'NEW_SALT_INVALID': NewSaltInvalidError,
    'NEW_SETTINGS_INVALID': NewSettingsInvalidError,
    'OFFSET_INVALID': OffsetInvalidError,
    'OFFSET_PEER_ID_INVALID': OffsetPeerIdInvalidError,
    'PACK_SHORT_NAME_INVALID': PackShortNameInvalidError,
    'PACK_SHORT_NAME_OCCUPIED': PackShortNameOccupiedError,
    'PARTICIPANTS_TOO_FEW': ParticipantsTooFewError,
    'PARTICIPANT_VERSION_OUTDATED': ParticipantVersionOutdatedError,
    'PASSWORD_EMPTY': PasswordEmptyError,
    'PASSWORD_HASH_INVALID': PasswordHashInvalidError,
    'PEER_FLOOD': PeerFloodError,
    'PEER_ID_INVALID': PeerIdInvalidError,
    'PEER_ID_NOT_SUPPORTED': PeerIdNotSupportedError,
    'PERSISTENT_TIMESTAMP_EMPTY': PersistentTimestampEmptyError,
    'PERSISTENT_TIMESTAMP_INVALID': PersistentTimestampInvalidError,
    'PHONE_CODE_EMPTY': PhoneCodeEmptyError,
    'PHONE_CODE_EXPIRED': PhoneCodeExpiredError,
    'PHONE_CODE_HASH_EMPTY': PhoneCodeHashEmptyError,
    'PHONE_CODE_INVALID': PhoneCodeInvalidError,
    'PHONE_NUMBER_APP_SIGNUP_FORBIDDEN': PhoneNumberAppSignupForbiddenError,
    'PHONE_NUMBER_BANNED': PhoneNumberBannedError,
    'PHONE_NUMBER_FLOOD': PhoneNumberFloodError,
    'PHONE_NUMBER_INVALID': PhoneNumberInvalidError,
    'PHONE_NUMBER_OCCUPIED': PhoneNumberOccupiedError,
    'PHONE_NUMBER_UNOCCUPIED': PhoneNumberUnoccupiedError,
    'PHONE_PASSWORD_FLOOD': PhonePasswordFloodError,
    'PHONE_PASSWORD_PROTECTED': PhonePasswordProtectedError,
    'PHOTO_CROP_SIZE_SMALL': PhotoCropSizeSmallError,
    'PHOTO_EXT_INVALID': PhotoExtInvalidError,
    'PHOTO_INVALID': PhotoInvalidError,
    'PHOTO_INVALID_DIMENSIONS': PhotoInvalidDimensionsError,
    'PRIVACY_KEY_INVALID': PrivacyKeyInvalidError,
    'QUERY_ID_EMPTY': QueryIdEmptyError,
    'QUERY_ID_INVALID': QueryIdInvalidError,
    'QUERY_TOO_SHORT': QueryTooShortError,
    'RANDOM_ID_INVALID': RandomIdInvalidError,
    'RANDOM_LENGTH_INVALID': RandomLengthInvalidError,
    'RANGES_INVALID': RangesInvalidError,
    'REPLY_MARKUP_INVALID': ReplyMarkupInvalidError,
    'RESULT_TYPE_INVALID': ResultTypeInvalidError,
    'RPC_CALL_FAIL': RpcCallFailError,
    'RPC_MCGET_FAIL': RpcMcgetFailError,
    'RSA_DECRYPT_FAILED': RsaDecryptFailedError,
    'SEARCH_QUERY_EMPTY': SearchQueryEmptyError,
    'SEND_MESSAGE_TYPE_INVALID': SendMessageTypeInvalidError,
    'SHA256_HASH_INVALID': Sha256HashInvalidError,
    'START_PARAM_EMPTY': StartParamEmptyError,
    'START_PARAM_INVALID': StartParamInvalidError,
    'STICKERSET_INVALID': StickersetInvalidError,
    'STICKERS_EMPTY': StickersEmptyError,
    'STICKER_EMOJI_INVALID': StickerEmojiInvalidError,
    'STICKER_FILE_INVALID': StickerFileInvalidError,
    'STICKER_ID_INVALID': StickerIdInvalidError,
    'STICKER_INVALID': StickerInvalidError,
    'STICKER_PNG_DIMENSIONS': StickerPngDimensionsError,
    'TEMP_AUTH_KEY_EMPTY': TempAuthKeyEmptyError,
    'TMP_PASSWORD_DISABLED': TmpPasswordDisabledError,
    'TOKEN_INVALID': TokenInvalidError,
    'TTL_DAYS_INVALID': TtlDaysInvalidError,
    'TYPES_EMPTY': TypesEmptyError,
    'TYPE_CONSTRUCTOR_INVALID': TypeConstructorInvalidError,
    'USERNAME_INVALID': UsernameInvalidError,
    'USERNAME_NOT_MODIFIED': UsernameNotModifiedError,
    'USERNAME_NOT_OCCUPIED': UsernameNotOccupiedError,
    'USERNAME_OCCUPIED': UsernameOccupiedError,
    'USERS_TOO_FEW': UsersTooFewError,
    'USERS_TOO_MUCH': UsersTooMuchError,
    'USER_ADMIN_INVALID': UserAdminInvalidError,
    'USER_ALREADY_PARTICIPANT': UserAlreadyParticipantError,
    'USER_BANNED_IN_CHANNEL': UserBannedInChannelError,
    'USER_BLOCKED': UserBlockedError,
    'USER_BOT': UserBotError,
    'USER_BOT_INVALID': UserBotInvalidError,
    'USER_BOT_REQUIRED': UserBotRequiredError,
    'USER_CREATOR': UserCreatorError,
    'USER_ID_INVALID': UserIdInvalidError,
    'USER_IS_BLOCKED': UserIsBlockedError,
    'USER_IS_BOT': UserIsBotError,
    'USER_KICKED': UserKickedError,
    'USER_NOT_MUTUAL_CONTACT': UserNotMutualContactError,
    'USER_NOT_PARTICIPANT': UserNotParticipantError,
    'WC_CONVERT_URL_INVALID': WcConvertUrlInvalidError,
    'WEBPAGE_CURL_FAILED': WebpageCurlFailedError,
    'WEBPAGE_MEDIA_EMPTY': WebpageMediaEmptyError,
    'YOU_BLOCKED_USER': YouBlockedUserError,
    'CHANNEL_PUBLIC_GROUP_NA': ChannelPublicGroupNaError,
    'CHAT_ADMIN_INVITE_REQUIRED': ChatAdminInviteRequiredError,
    'CHAT_ADMIN_REQUIRED': ChatAdminRequiredError,
    'CHAT_SEND_GIFS_FORBIDDEN': ChatSendGifsForbiddenError,
    'CHAT_SEND_MEDIA_FORBIDDEN': ChatSendMediaForbiddenError,
    'CHAT_SEND_STICKERS_FORBIDDEN': ChatSendStickersForbiddenError,
    'CHAT_WRITE_FORBIDDEN': ChatWriteForbiddenError,
    'MESSAGE_AUTHOR_REQUIRED': MessageAuthorRequiredError,
    'MESSAGE_DELETE_FORBIDDEN': MessageDeleteForbiddenError,
    'RIGHT_FORBIDDEN': RightForbiddenError,
    'USER_BOT_INVALID': UserBotInvalidError,
    'USER_CHANNELS_TOO_MUCH': UserChannelsTooMuchError,
    'USER_IS_BLOCKED': UserIsBlockedError,
    'USER_NOT_MUTUAL_CONTACT': UserNotMutualContactError,
    'USER_PRIVACY_RESTRICTED': UserPrivacyRestrictedError,
    'USER_RESTRICTED': UserRestrictedError,
    'AUTH_RESTART': AuthRestartError,
    'CALL_OCCUPY_FAILED': CallOccupyFailedError,
    'ENCRYPTION_OCCUPY_FAILED': EncryptionOccupyFailedError,
    'HISTORY_GET_FAILED': HistoryGetFailedError,
    'MEMBER_NO_LOCATION': MemberNoLocationError,
    'MEMBER_OCCUPY_PRIMARY_LOC_FAILED': MemberOccupyPrimaryLocFailedError,
    'NEED_CHAT_INVALID': NeedChatInvalidError,
    'NEED_MEMBER_INVALID': NeedMemberInvalidError,
    'PARTICIPANT_CALL_FAILED': ParticipantCallFailedError,
    'PERSISTENT_TIMESTAMP_OUTDATED': PersistentTimestampOutdatedError,
    'PTS_CHANGE_EMPTY': PtsChangeEmptyError,
    'RANDOM_ID_DUPLICATE': RandomIdDuplicateError,
    'REG_ID_GENERATE_FAILED': RegIdGenerateFailedError,
    'STORAGE_CHECK_FAILED': StorageCheckFailedError,
    'STORE_INVALID_SCALAR_TYPE': StoreInvalidScalarTypeError,
    'UNKNOWN_METHOD': UnknownMethodError,
}
