"""Various helpers not related to the Telegram API itself"""
import asyncio
import os
import struct
from hashlib import sha1, sha256


# region Multiple utilities


def generate_random_long(signed=True):
    """Generates a random long integer (8 bytes), which is optionally signed"""
    return int.from_bytes(os.urandom(8), signed=signed, byteorder='little')


def ensure_parent_dir_exists(file_path):
    """Ensures that the parent directory exists"""
    parent = os.path.dirname(file_path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def add_surrogate(text):
    return ''.join(
        # SMP -> Surrogate Pairs (Telegram offsets are calculated with these).
        # See https://en.wikipedia.org/wiki/Plane_(Unicode)#Overview for more.
        ''.join(chr(y) for y in struct.unpack('<HH', x.encode('utf-16le')))
        if (0x10000 <= ord(x) <= 0x10FFFF) else x for x in text
    )


def del_surrogate(text):
    return text.encode('utf-16', 'surrogatepass').decode('utf-16')


# endregion

# region Cryptographic related utils


def generate_key_data_from_nonce(server_nonce, new_nonce):
    """Generates the key data corresponding to the given nonce"""
    server_nonce = server_nonce.to_bytes(16, 'little', signed=True)
    new_nonce = new_nonce.to_bytes(32, 'little', signed=True)
    hash1 = sha1(new_nonce + server_nonce).digest()
    hash2 = sha1(server_nonce + new_nonce).digest()
    hash3 = sha1(new_nonce + new_nonce).digest()

    key = hash1 + hash2[:12]
    iv = hash2[12:20] + hash3 + new_nonce[:4]
    return key, iv


def get_password_hash(pw, current_salt):
    """Gets the password hash for the two-step verification.
       current_salt should be the byte array provided by
       invoking GetPasswordRequest()
    """

    # Passwords are encoded as UTF-8
    # At https://github.com/DrKLO/Telegram/blob/e31388
    # src/main/java/org/telegram/ui/LoginActivity.java#L2003
    data = pw.encode('utf-8')

    pw_hash = current_salt + data + current_salt
    return sha256(pw_hash).digest()

# endregion

# region Custom Classes

class TotalList(list):
    """
    A list with an extra `total` property, which may not match its `len`
    since the total represents the total amount of items *available*
    somewhere else, not the items *in this list*.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.total = 0

    def __str__(self):
        return '[{}, total={}]'.format(
            ', '.join(str(x) for x in self), self.total)

    def __repr__(self):
        return '[{}, total={}]'.format(
            ', '.join(repr(x) for x in self), self.total)


class _ReadyQueue:
    """
    A queue list that supports an arbitrary cancellation token for `get`.
    """
    def __init__(self, loop):
        self._list = []
        self._loop = loop
        self._ready = asyncio.Event(loop=loop)

    def append(self, item):
        self._list.append(item)
        self._ready.set()

    def extend(self, items):
        self._list.extend(items)
        self._ready.set()

    async def get(self, cancellation):
        """
        Returns a list of all the items added to the queue until now and
        clears the list from the queue itself. Returns ``None`` if cancelled.
        """
        ready = self._loop.create_task(self._ready.wait())
        try:
            done, pending = await asyncio.wait(
                [ready, cancellation],
                return_when=asyncio.FIRST_COMPLETED,
                loop=self._loop
            )
        except asyncio.CancelledError:
            done = [cancellation]

        if cancellation in done:
            ready.cancel()
            return None

        result = self._list
        self._list = []
        self._ready.clear()
        return result

# endregion
