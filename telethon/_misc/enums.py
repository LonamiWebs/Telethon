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
