"""Various helpers not related to the Telegram API itself"""
import asyncio
import io
import enum
import os
import struct
import inspect
import logging
import functools
import sys
from pathlib import Path
from hashlib import sha1


class _EntityType(enum.Enum):
    USER = 0
    CHAT = 1
    CHANNEL = 2


_log = logging.getLogger(__name__)


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
    Strips whitespace from the given surrogated text modifying the provided
    entities, also removing any empty (0-length) entities.

    This assumes that the length of entities is greater or equal to 0, and
    that no entity is out of bounds.
    """
    if not entities:
        return text.strip()

    len_ori = len(text)
    text = text.lstrip()
    left_offset = len_ori - len(text)
    text = text.rstrip()
    len_final = len(text)

    for i in reversed(range(len(entities))):
        e = entities[i]
        if e.length == 0:
            del entities[i]
            continue

        if e.offset + e.length > left_offset:
            if e.offset >= left_offset:
                #  0 1|2 3 4 5       |       0 1|2 3 4 5
                #     ^     ^        |          ^
                #   lo(2)  o(5)      |      o(2)/lo(2)
                e.offset -= left_offset
                #     |0 1 2 3       |          |0 1 2 3
                #           ^        |          ^
                #     o=o-lo(3=5-2)  |    o=o-lo(0=2-2)
            else:
                # e.offset < left_offset and e.offset + e.length > left_offset
                #  0 1 2 3|4 5 6 7 8 9 10
                #   ^     ^           ^
                #  o(1) lo(4)      o+l(1+9)
                e.length = e.offset + e.length - left_offset
                e.offset = 0
                #         |0 1 2 3 4 5 6
                #         ^           ^
                #        o(0)  o+l=0+o+l-lo(6=0+6=0+1+9-4)
        else:
            # e.offset + e.length <= left_offset
            #   0 1 2 3|4 5
            #  ^       ^
            # o(0)   o+l(4)
            #        lo(4)
            del entities[i]
            continue

        if e.offset + e.length <= len_final:
            # |0 1 2 3 4 5 6 7 8 9
            #   ^                 ^
            #  o(1)       o+l(1+9)/lf(10)
            continue
        if e.offset >= len_final:
            # |0 1 2 3 4
            #           ^
            #       o(5)/lf(5)
            del entities[i]
        else:
            # e.offset < len_final and e.offset + e.length > len_final
            # |0 1 2 3 4 5 (6) (7) (8) (9)
            #   ^         ^           ^
            #  o(1)     lf(6)      o+l(1+8)
            e.length = len_final - e.offset
            # |0 1 2 3 4 5
            #   ^         ^
            #  o(1) o+l=o+lf-o=lf(6=1+5=1+6-1)

    return text


def retry_range(retries, force_retry=True):
    """
    Generates an integer sequence starting from 1. If `retries` is
    not a zero or a positive integer value, the sequence will be
    infinite, otherwise it will end at `retries + 1`.
    """

    # We need at least one iteration even if the retries are 0
    # when force_retry is True.
    if force_retry and not (retries is None or retries < 0):
        retries += 1

    attempt = 0
    while attempt != retries:
        attempt += 1
        yield attempt
        


async def _maybe_await(value):
    if inspect.isawaitable(value):
        return await value
    else:
        return value


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
            # See: https://github.com/python/cpython/blob/12d3061c7819a73d891dcce44327410eaf0e1bc2/Lib/asyncio/futures.py#L265
            #
            # Happens with _asyncio.Task instances (in "Task cancelling" state)
            # trying to SIGINT the program right during initial connection, on
            # _recv_loop coroutine (but we're creating its task explicitly with
            # a loop, so how can it bug out like this?).
            #
            # Since we're aware of this error there's no point in logging it.
            # *May* be https://bugs.python.org/issue37172
            pass
        except AssertionError as e:
            # In Python 3.6, the above RuntimeError is an AssertionError
            # See https://github.com/python/cpython/blob/7df32f844efed33ca781a016017eab7050263b90/Lib/asyncio/futures.py#L328
            if e.args != ("yield from wasn't used with future",):
                log.exception('Unhandled exception from %s after cancelling '
                              '%s (%s)', name, type(task), task)
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


class _FileStream(io.IOBase):
    """
    Proxy around things that represent a file and need to be used as streams
    which may or not need to be closed.

    This will handle `pathlib.Path`, `str` paths, in-memory `bytes`, and
    anything IO-like (including `aiofiles`).

    It also provides access to the name and file size (also necessary).
    """
    def __init__(self, file, *, file_size=None):
        if isinstance(file, Path):
            file = str(file.absolute())

        self._file = file
        self._name = None
        self._size = file_size
        self._stream = None
        self._close_stream = None

    async def __aenter__(self):
        if isinstance(self._file, str):
            self._name = os.path.basename(self._file)
            self._size = os.path.getsize(self._file)
            self._stream = open(self._file, 'rb')
            self._close_stream = True

        elif isinstance(self._file, bytes):
            self._size = len(self._file)
            self._stream = io.BytesIO(self._file)
            self._close_stream = True

        elif not callable(getattr(self._file, 'read', None)):
            raise TypeError('file description should have a `read` method')

        elif self._size is not None:
            self._name = getattr(self._file, 'name', None)
            self._stream = self._file
            self._close_stream = False

        else:
            if callable(getattr(self._file, 'seekable', None)):
                seekable = await _maybe_await(self._file.seekable())
            else:
                seekable = False

            if seekable:
                pos = await _maybe_await(self._file.tell())
                await _maybe_await(self._file.seek(0, os.SEEK_END))
                self._size = await _maybe_await(self._file.tell())
                await _maybe_await(self._file.seek(pos, os.SEEK_SET))
                self._stream = self._file
                self._close_stream = False
            else:
                _log.warning(
                    'Could not determine file size beforehand so the entire '
                    'file will be read in-memory')

                data = await _maybe_await(self._file.read())
                self._size = len(data)
                self._stream = io.BytesIO(data)
                self._close_stream = True

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._close_stream and self._stream:
            await _maybe_await(self._stream.close())

    @property
    def file_size(self):
        return self._size

    @property
    def name(self):
        return self._name

    # Proxy all the methods. Doesn't need to be readable (makes multiline edits easier)
    def read(self, *args, **kwargs): return self._stream.read(*args, **kwargs)
    def readinto(self, *args, **kwargs): return self._stream.readinto(*args, **kwargs)
    def write(self, *args, **kwargs): return self._stream.write(*args, **kwargs)
    def fileno(self, *args, **kwargs): return self._stream.fileno(*args, **kwargs)
    def flush(self, *args, **kwargs): return self._stream.flush(*args, **kwargs)
    def isatty(self, *args, **kwargs): return self._stream.isatty(*args, **kwargs)
    def readable(self, *args, **kwargs): return self._stream.readable(*args, **kwargs)
    def readline(self, *args, **kwargs): return self._stream.readline(*args, **kwargs)
    def readlines(self, *args, **kwargs): return self._stream.readlines(*args, **kwargs)
    def seek(self, *args, **kwargs): return self._stream.seek(*args, **kwargs)
    def seekable(self, *args, **kwargs): return self._stream.seekable(*args, **kwargs)
    def tell(self, *args, **kwargs): return self._stream.tell(*args, **kwargs)
    def truncate(self, *args, **kwargs): return self._stream.truncate(*args, **kwargs)
    def writable(self, *args, **kwargs): return self._stream.writable(*args, **kwargs)
    def writelines(self, *args, **kwargs): return self._stream.writelines(*args, **kwargs)

    # close is special because it will be called by __del__ but we do NOT
    # want to close the file unless we have to (we're just a wrapper).
    # Instead, we do nothing (we should be used through the decorator which
    # has its own mechanism to close the file correctly).
    def close(self, *args, **kwargs):
        pass

# endregion

def get_running_loop():
    if sys.version_info[:2] <= (3, 6):
        return asyncio._get_running_loop()

    return asyncio.get_running_loop()
