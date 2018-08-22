import base64
import ipaddress
import struct

from .memory import MemorySession
from ..crypto import AuthKey

CURRENT_VERSION = '1'


class StringSession(MemorySession):
    """
    This minimal session file can be easily saved and loaded as a string.

    It is thought to be used where you don't want to create any on-disk
    files but would still like to be able to save and load existing sessions
    by other means.

    You can use custom `encode` and `decode` functions, if present:

    * `encode` definition must be ``def encode(value: bytes) -> str:``.
    * `decode` definition must be ``def decode(value: str) -> bytes:``.
    """
    encode = lambda x: base64.urlsafe_b64encode(x).decode('ascii')
    decode = base64.urlsafe_b64decode

    def __init__(self, string=None):
        super().__init__()
        if string:
            if string[0] != CURRENT_VERSION:
                raise ValueError('Not a valid string')

            string = string[1:]
            ip_len = 4 if len(string) == 352 else 16
            self._dc_id, ip, self._port, key = struct.unpack(
                '>B{}sH256s'.format(ip_len), StringSession.decode(string))

            self._server_address = ipaddress.ip_address(ip).compressed
            if any(key):
                self._auth_key = AuthKey(key)

    def save(self):
        if not self._auth_key:
            return ''

        ip = ipaddress.ip_address(self._server_address).packed
        return CURRENT_VERSION + StringSession.encode(struct.pack(
            '>B{}sH256s'.format(len(ip)),
            self._dc_id,
            ip,
            self._port,
            self._auth_key.key
        ))
