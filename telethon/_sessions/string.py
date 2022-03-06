import base64
import ipaddress
import struct

from .abstract import Session
from .memory import MemorySession
from .types import DataCenter, ChannelState, SessionState, Entity

_STRUCT_PREFORMAT = '>B{}sH256s'

CURRENT_VERSION = '1'


class StringSession(MemorySession):
    """
    This session file can be easily saved and loaded as a string. According
    to the initial design, it contains only the data that is necessary for
    successful connection and authentication, so takeout ID is not stored.

    It is thought to be used where you don't want to create any on-disk
    files but would still like to be able to save and load existing sessions
    by other means.

    You can use custom `encode` and `decode` functions, if present:

    * `encode` definition must be ``def encode(value: bytes) -> str:``.
    * `decode` definition must be ``def decode(value: str) -> bytes:``.
    """
    def __init__(self, string: str = None):
        super().__init__()
        if string:
            if string[0] != CURRENT_VERSION:
                raise ValueError('Not a valid string')

            string = string[1:]
            ip_len = 4 if len(string) == 352 else 16
            dc_id, ip, port, key = struct.unpack(
                _STRUCT_PREFORMAT.format(ip_len), StringSession.decode(string))

            self.state = SessionState(
                dc_id=dc_id,
                user_id=0,
                bot=False,
                pts=0,
                qts=0,
                date=0,
                seq=0,
                takeout_id=0
            )
            if ip_len == 4:
                ipv4 = int.from_bytes(ip, 'big',  signed=False)
                ipv6 = None
            else:
                ipv4 = None
                ipv6 = int.from_bytes(ip, 'big', signed=False)

            self.dcs[dc_id] = DataCenter(
                id=dc_id,
                ipv4=ipv4,
                ipv6=ipv6,
                port=port,
                auth=key
            )

    @staticmethod
    def encode(x: bytes) -> str:
        return base64.urlsafe_b64encode(x).decode('ascii')

    @staticmethod
    def decode(x: str) -> bytes:
        return base64.urlsafe_b64decode(x)

    def save(self: Session):
        if not self.state:
            return ''

        if self.dcs[self.state.dc_id].ipv6 is not None:
            ip = self.dcs[self.state.dc_id].ipv6.to_bytes(16, 'big', signed=False)
        else:
            ip = self.dcs[self.state.dc_id].ipv4.to_bytes(4, 'big', signed=False)

        return CURRENT_VERSION + StringSession.encode(struct.pack(
            _STRUCT_PREFORMAT.format(len(ip)),
            self.state.dc_id,
            ip,
            self.dcs[self.state.dc_id].port,
            self.dcs[self.state.dc_id].auth
        ))
