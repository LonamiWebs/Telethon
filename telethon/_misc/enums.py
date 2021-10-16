from enum import Enum


class ConnectionMode(Enum):
    FULL = 'full'
    INTERMEDIATE = 'intermediate'
    ABRIDGED = 'abridged'
    OBFUSCATED = 'obfuscated'
    HTTP = 'http'


class Participant(Enum):
    ADMIN = 'admin'
    BOT = 'bot'
    KICKED = 'kicked'
    BANNED = 'banned'
    CONTACT = 'contact'


class Action(Enum):
    TYPING = 'typing'
    CONTACT = 'contact'
    GAME = 'game'
    LOCATION = 'location'
    STICKER = 'sticker'
    RECORD_AUDIO = 'record-audio'
    RECORD_VOICE = RECORD_AUDIO
    RECORD_ROUND = 'record-round'
    RECORD_VIDEO = 'record-video'
    AUDIO = 'audio'
    VOICE = AUDIO
    SONG = AUDIO
    ROUND = 'round'
    VIDEO = 'video'
    PHOTO = 'photo'
    DOCUMENT = 'document'
    FILE = DOCUMENT
    CANCEL = 'cancel'


def _mk_parser(cls):
    def parser(value):
        if isinstance(value, cls):
            return value
        elif isinstance(value, str):
            for variant in cls:
                if value == variant.value:
                    return variant

            raise ValueError(f'unknown {cls.__name__}: {value!r}')
        else:
            raise TypeError(f'not a valid {cls.__name__}: {type(value).__name__!r}')

    return parser


parse_conn_mode = _mk_parser(ConnectionMode)
parse_participant = _mk_parser(Participant)
parse_typing_action = _mk_parser(Action)
