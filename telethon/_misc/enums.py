from enum import Enum


class ConnectionMode(Enum):
    FULL = 'full'
    INTERMEDIATE = 'intermediate'
    ABRIDGED = 'abridged'
    OBFUSCATED = 'obfuscated'
    HTTP = 'http'


def parse_conn_mode(mode):
    if isinstance(mode, ConnectionMode):
        return mode
    elif isinstance(mode, str):
        for cm in ConnectionMode:
            if mode == cm.value:
                return cm

        raise ValueError(f'unknown connection mode: {mode!r}')
    else:
        raise TypeError(f'not a valid connection mode: {type(mode).__name__!r}')
