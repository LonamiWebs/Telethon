import struct
from datetime import datetime, date
from threading import Event


class TLObject:
    def __init__(self):
        self.confirm_received = Event()
        self.rpc_error = None
        self.result = None

        # These should be overrode
        self.content_related = False  # Only requests/functions/queries are

    # These should not be overrode
    @staticmethod
    def pretty_format(obj, indent=None):
        """Pretty formats the given object as a string which is returned.
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
            elif isinstance(obj, datetime):
                return 'datetime.utcfromtimestamp({})'.format(
                    int(obj.timestamp())
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

            elif isinstance(obj, datetime):
                result.append('datetime.utcfromtimestamp(')
                result.append(repr(int(obj.timestamp())))
                result.append(')')

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
        if not dt:
            return b'\0\0\0\0'

        if isinstance(dt, datetime):
            dt = int(dt.timestamp())
        elif isinstance(dt, date):
            dt = int(datetime(dt.year, dt.month, dt.day).timestamp())
        elif isinstance(dt, float):
            dt = int(dt)

        if isinstance(dt, int):
            return struct.pack('<I', dt)

        raise TypeError('Cannot interpret "{}" as a date.'.format(dt))

    # These are nearly always the same for all subclasses
    def on_response(self, reader):
        self.result = reader.tgread_object()

    def __eq__(self, o):
        return isinstance(o, type(self)) and self.to_dict() == o.to_dict()

    def __ne__(self, o):
        return not isinstance(o, type(self)) or self.to_dict() != o.to_dict()

    def __str__(self):
        return TLObject.pretty_format(self)

    def stringify(self):
        return TLObject.pretty_format(self, indent=0)

    # These should be overrode
    def resolve(self, client, utils):
        pass

    def to_dict(self):
        return {}

    def __bytes__(self):
        return b''

    @staticmethod
    def from_reader(reader):
        return TLObject()
