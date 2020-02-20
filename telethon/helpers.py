"""Various helpers not related to the Telegram API itself"""
import asyncio
import enum
import os
import struct
from hashlib import sha1


class _EntityType(enum.Enum):
    USER = 0
    CHAT = 1
    CHANNEL = 2


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


def within_surrogate(text, index, *, length=None):
    """
    `True` if ``index`` is within a surrogate (before and after it, not at!).
    """
    if length is None:
        length = len(text)

    return (
            1 < index < len(text) and  # in bounds
            '\ud800' <= text[index - 1] <= '\udfff' and  # previous is
            '\ud800' <= text[index] <= '\udfff'  # current is
    )


def strip_text(text, entities):
    """
    Strips whitespace from the given text modifying the provided entities.

    This assumes that there are no overlapping entities, that their length
    is greater or equal to one, and that their length is not out of bounds.
    """
    if not entities:
        return text.strip()

    while text and text[-1].isspace():
        e = entities[-1]
        if e.offset + e.length == len(text):
            if e.length == 1:
                del entities[-1]
                if not entities:
                    return text.strip()
            else:
                e.length -= 1
        text = text[:-1]

    while text and text[0].isspace():
        for i in reversed(range(len(entities))):
            e = entities[i]
            if e.offset != 0:
                e.offset -= 1
                continue

            if e.length == 1:
                del entities[0]
                if not entities:
                    return text.lstrip()
            else:
                e.length -= 1

        text = text[1:]

    return text


def retry_range(retries):
    """
    Generates an integer sequence starting from 1. If `retries` is
    not a zero or a positive integer value, the sequence will be
    infinite, otherwise it will end at `retries + 1`.
    """
    yield 1
    attempt = 0
    while attempt != retries:
        attempt += 1
        yield 1 + attempt


async def _cancel(log, **tasks):
    """
    Helper to cancel one or more tasks gracefully, logging exceptions.
    """
    for name, task in tasks.items():
        if not task:
            continue

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        except RuntimeError:
            # Probably: RuntimeError: await wasn't used with future
            #
            # Happens with _asyncio.Task instances (in "Task cancelling" state)
            # trying to SIGINT the program right during initial connection, on
            # _recv_loop coroutine (but we're creating its task explicitly with
            # a loop, so how can it bug out like this?).
            #
            # Since we're aware of this error there's no point in logging it.
            # *May* be https://bugs.python.org/issue37172
            pass
        except Exception:
            log.exception('Unhandled exception from %s after cancelling '
                          '%s (%s)', name, type(task), task)


def _sync_enter(self):
    """
    Helps to cut boilerplate on async context
    managers that offer synchronous variants.
    """
    if hasattr(self, 'loop'):
        loop = self.loop
    else:
        loop = self._client.loop

    if loop.is_running():
        raise RuntimeError(
            'You must use "async with" if the event loop '
            'is running (i.e. you are inside an "async def")'
        )

    return loop.run_until_complete(self.__aenter__())


def _sync_exit(self, *args):
    if hasattr(self, 'loop'):
        loop = self.loop
    else:
        loop = self._client.loop

    return loop.run_until_complete(self.__aexit__(*args))


def _entity_type(entity):
    # This could be a `utils` method that just ran a few `isinstance` on
    # `utils.get_peer(...)`'s result. However, there are *a lot* of auto
    # casts going on, plenty of calls and temporary short-lived objects.
    #
    # So we just check if a string is in the class name.
    # Still, assert that it's the right type to not return false results.
    try:
        if entity.SUBCLASS_OF_ID not in (
                0x2d45687,  # crc32(b'Peer')
                0xc91c90b6,  # crc32(b'InputPeer')
                0xe669bf46,  # crc32(b'InputUser')
                0x40f202fd,  # crc32(b'InputChannel')
                0x2da17977,  # crc32(b'User')
                0xc5af5d94,  # crc32(b'Chat')
                0x1f4661b9,  # crc32(b'UserFull')
                0xd49a2697,  # crc32(b'ChatFull')
        ):
            raise TypeError('{} does not have any entity type'.format(entity))
    except AttributeError:
        raise TypeError('{} is not a TLObject, cannot determine entity type'.format(entity))

    name = entity.__class__.__name__
    if 'User' in name:
        return _EntityType.USER
    elif 'Chat' in name:
        return _EntityType.CHAT
    elif 'Channel' in name:
        return _EntityType.CHANNEL
    elif 'Self' in name:
        return _EntityType.USER

    # 'Empty' in name or not found, we don't care, not a valid entity.
    raise TypeError('{} does not have any entity type'.format(entity))

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


# endregion

# region Custom Classes


class TotalList(list):
    """
    A list with an extra `total` property, which may not match its `len`
    since the total represents the total amount of items *available*
    somewhere else, not the items *in this list*.

    Examples:

        .. code-block:: python

            # Telethon returns these lists in some cases (for example,
            # only when a chunk is returned, but the "total" count
            # is available).
            result = await client.get_messages(chat, limit=10)

            print(result.total)  # large number
            print(len(result))  # 10
            print(result[0])  # latest message

            for x in result:  # show the 10 messages
                print(x.text)

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


# endregion
