import base64
import json
import struct
from datetime import datetime, date, timedelta, timezone
import time

_EPOCH_NAIVE = datetime(*time.gmtime(0)[:6])
_EPOCH_NAIVE_LOCAL = datetime(*time.localtime(0)[:6])
_EPOCH = _EPOCH_NAIVE.replace(tzinfo=timezone.utc)


def _datetime_to_timestamp(dt):
    # If no timezone is specified, it is assumed to be in utc zone
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    # We use .total_seconds() method instead of simply dt.timestamp(), 
    # because on Windows the latter raises OSError on datetimes ~< datetime(1970,1,1)
    return int((dt - _EPOCH).total_seconds())


def _json_default(value):
    if isinstance(value, bytes):
        return base64.b64encode(value).decode('ascii')
    elif isinstance(value, datetime):
        return value.isoformat()
    else:
        return repr(value)


class TLObject:
    CONSTRUCTOR_ID = None
    SUBCLASS_OF_ID = None

    @staticmethod
    def pretty_format(obj, indent=None):
        """
        Pretty formats the given object as a string which is returned.
        If indent is None, a single line will be returned.
        """
        if indent is None:
            if isinstance(obj, TLObject):
                obj = obj.to_dict()

            if isinstance(obj, dict):
                return '{}({})'.format(obj.get('_', 'dict'), ', '.join(
                    '{}={}'.format(k, TLObject.pretty_format(v))
                    for k, v in obj.items() if k != '_'
                ))
            elif isinstance(obj, str) or isinstance(obj, bytes):
                return repr(obj)
            elif hasattr(obj, '__iter__'):
                return '[{}]'.format(
                    ', '.join(TLObject.pretty_format(x) for x in obj)
                )
            else:
                return repr(obj)
        else:
            result = []
            if isinstance(obj, TLObject):
                obj = obj.to_dict()

            if isinstance(obj, dict):
                result.append(obj.get('_', 'dict'))
                result.append('(')
                if obj:
                    result.append('\n')
                    indent += 1
                    for k, v in obj.items():
                        if k == '_':
                            continue
                        result.append('\t' * indent)
                        result.append(k)
                        result.append('=')
                        result.append(TLObject.pretty_format(v, indent))
                        result.append(',\n')
                    result.pop()  # last ',\n'
                    indent -= 1
                    result.append('\n')
                    result.append('\t' * indent)
                result.append(')')

            elif isinstance(obj, str) or isinstance(obj, bytes):
                result.append(repr(obj))

            elif hasattr(obj, '__iter__'):
                result.append('[\n')
                indent += 1
                for x in obj:
                    result.append('\t' * indent)
                    result.append(TLObject.pretty_format(x, indent))
                    result.append(',\n')
                indent -= 1
                result.append('\t' * indent)
                result.append(']')

            else:
                result.append(repr(obj))

            return ''.join(result)

    @staticmethod
    def serialize_bytes(data):
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
    def serialize_datetime(dt):
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

    def __str__(self):
        return TLObject.pretty_format(self)

    def stringify(self):
        return TLObject.pretty_format(self, indent=0)

    def to_dict(self):
        raise NotImplementedError

    def to_json(self, fp=None, default=_json_default, **kwargs):
        """
        Represent the current `TLObject` as JSON.

        If ``fp`` is given, the JSON will be dumped to said
        file pointer, otherwise a JSON string will be returned.

        Note that bytes and datetimes cannot be represented
        in JSON, so if those are found, they will be base64
        encoded and ISO-formatted, respectively, by default.
        """
        d = self.to_dict()
        if fp:
            return json.dump(d, fp, default=default, **kwargs)
        else:
            return json.dumps(d, default=default, **kwargs)

    def __bytes__(self):
        try:
            return self._bytes()
        except AttributeError:
            # If a type is wrong (e.g. expected `TLObject` but `int` was
            # provided) it will try to access `._bytes()`, which will fail
            # with `AttributeError`. This occurs in fact because the type
            # was wrong, so raise the correct error type.
            raise TypeError('a TLObject was expected but found something else')

    # Custom objects will call `(...)._bytes()` and not `bytes(...)` so that
    # if the wrong type is used (e.g. `int`) we won't try allocating a huge
    # amount of data, which would cause a `MemoryError`.
    def _bytes(self):
        raise NotImplementedError

    @classmethod
    def from_reader(cls, reader):
        raise NotImplementedError


class TLRequest(TLObject):
    """
    Represents a content-related `TLObject` (a request that can be sent).
    """
    @staticmethod
    def read_result(reader):
        return reader.tgread_object()

    async def resolve(self, client, utils):
        pass
