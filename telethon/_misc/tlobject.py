import base64
import json
import struct
from datetime import datetime, date, timedelta, timezone
import time
from .helpers import pretty_print

_EPOCH_NAIVE = datetime(*time.gmtime(0)[:6])
_EPOCH_NAIVE_LOCAL = datetime(*time.localtime(0)[:6])
_EPOCH = _EPOCH_NAIVE.replace(tzinfo=timezone.utc)


def _datetime_to_timestamp(dt):
    # If no timezone is specified, it is assumed to be in utc zone
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    # We use .total_seconds() method instead of simply dt.timestamp(),
    # because on Windows the latter raises OSError on datetimes ~< datetime(1970,1,1)
    secs = int((dt - _EPOCH).total_seconds())
    # Make sure it's a valid signed 32 bit integer, as used by Telegram.
    # This does make very large dates wrap around, but it's the best we
    # can do with Telegram's limitations.
    return struct.unpack('i', struct.pack('I', secs & 0xffffffff))[0]


def _json_default(value):
    if isinstance(value, bytes):
        return base64.b64encode(value).decode('ascii')
    elif isinstance(value, datetime):
        return value.isoformat()
    else:
        return repr(value)


class TLObject:
    __slots__ = ()
    CONSTRUCTOR_ID = None
    SUBCLASS_OF_ID = None

    @staticmethod
    def _serialize_bytes(data):
        """Write bytes by using Telegram guidelines"""
        if not isinstance(data, bytes):
            if isinstance(data, str):
                data = data.encode('utf-8')
            else:
                raise TypeError(
                    'bytes or str expected, not {}'.format(type(data)))

        r = []
        if len(data) < 254:
            padding = (len(data) + 1) % 4
            if padding != 0:
                padding = 4 - padding

            r.append(bytes([len(data)]))
            r.append(data)

        else:
            padding = len(data) % 4
            if padding != 0:
                padding = 4 - padding

            r.append(bytes([
                254,
                len(data) % 256,
                (len(data) >> 8) % 256,
                (len(data) >> 16) % 256
            ]))
            r.append(data)

        r.append(bytes(padding))
        return b''.join(r)

    @staticmethod
    def _serialize_datetime(dt):
        if not dt and not isinstance(dt, timedelta):
            return b'\0\0\0\0'

        if isinstance(dt, datetime):
            dt = _datetime_to_timestamp(dt)
        elif isinstance(dt, date):
            dt = _datetime_to_timestamp(datetime(dt.year, dt.month, dt.day))
        elif isinstance(dt, float):
            dt = int(dt)
        elif isinstance(dt, timedelta):
            # Timezones are tricky. datetime.utcnow() + ... timestamp() works
            dt = _datetime_to_timestamp(datetime.utcnow() + dt)

        if isinstance(dt, int):
            return struct.pack('<i', dt)

        raise TypeError('Cannot interpret "{}" as a date.'.format(dt))

    def __eq__(self, o):
        return isinstance(o, type(self)) and self.to_dict() == o.to_dict()

    def __ne__(self, o):
        return not isinstance(o, type(self)) or self.to_dict() != o.to_dict()

    def __repr__(self):
        return pretty_print(self)

    def __str__(self):
        return pretty_print(self, max_depth=2)

    def stringify(self):
        return pretty_print(self, indent=0)

    def to_dict(self):
        res = {}
        pre = ('', 'fn.')[isinstance(self, TLRequest)]
        mod = self.__class__.__module__[self.__class__.__module__.rfind('.') + 1:]
        if mod in ('_tl', 'fn'):
            res['_'] = f'{pre}{self.__class__.__name__}'
        else:
            res['_'] = f'{pre}{mod}.{self.__class__.__name__}'

        for slot in self.__slots__:
            attr = getattr(self, slot)
            if isinstance(attr, list):
                res[slot] = [val.to_dict() if hasattr(val, 'to_dict') else val for val in attr]
            else:
                res[slot] = attr.to_dict() if hasattr(attr, 'to_dict') else attr

        return res

    def __bytes__(self):
        try:
            return self._bytes()
        except AttributeError:
            # If a type is wrong (e.g. expected `TLObject` but `int` was
            # provided) it will try to access `._bytes()`, which will fail
            # with `AttributeError`. This occurs in fact because the type
            # was wrong, so raise the correct error type.
            raise TypeError(f'a TLObject was expected but found {self!r}')

    # Custom objects will call `(...)._bytes()` and not `bytes(...)` so that
    # if the wrong type is used (e.g. `int`) we won't try allocating a huge
    # amount of data, which would cause a `MemoryError`.
    def _bytes(self):
        raise NotImplementedError

    @classmethod
    def _from_reader(cls, reader):
        raise NotImplementedError


class TLRequest(TLObject):
    """
    Represents a content-related `TLObject` (a request that can be sent).
    """
    @staticmethod
    def _read_result(reader):
        return reader.tgread_object()

    async def _resolve(self, client, utils):
        return self
