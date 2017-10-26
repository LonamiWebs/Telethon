from datetime import datetime
from threading import Event


class TLObject:
    def __init__(self):
        self.request_msg_id = 0  # Long

        self.confirm_received = Event()
        self.rpc_error = None

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
                return '{}({})'.format(type(obj).__name__, ', '.join(
                    '{}={}'.format(k, TLObject.pretty_format(v))
                    for k, v in obj.to_dict(recursive=False).items()
                ))
            if isinstance(obj, dict):
                return '{{{}}}'.format(', '.join(
                    '{}: {}'.format(k, TLObject.pretty_format(v))
                    for k, v in obj.items()
                ))
            elif isinstance(obj, str) or isinstance(obj, bytes):
                return repr(obj)
            elif hasattr(obj, '__iter__'):
                return '[{}]'.format(
                    ', '.join(TLObject.pretty_format(x) for x in obj)
                )
            elif isinstance(obj, datetime):
                return 'datetime.fromtimestamp({})'.format(obj.timestamp())
            else:
                return repr(obj)
        else:
            result = []
            if isinstance(obj, TLObject) or isinstance(obj, dict):
                if isinstance(obj, dict):
                    d = obj
                    start, end, sep = '{', '}', ': '
                else:
                    d = obj.to_dict(recursive=False)
                    start, end, sep = '(', ')', '='
                    result.append(type(obj).__name__)

                result.append(start)
                if d:
                    result.append('\n')
                    indent += 1
                    for k, v in d.items():
                        result.append('\t' * indent)
                        result.append(k)
                        result.append(sep)
                        result.append(TLObject.pretty_format(v, indent))
                        result.append(',\n')
                    result.pop()  # last ',\n'
                    indent -= 1
                    result.append('\n')
                    result.append('\t' * indent)
                result.append(end)

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
                result.append('datetime.fromtimestamp(')
                result.append(repr(obj.timestamp()))
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
                raise ValueError('bytes or str expected, not', type(data))

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

    # These should be overrode
    def to_dict(self, recursive=True):
        return {}

    def __bytes__(self):
        return b''

    @staticmethod
    def from_reader(reader):
        return TLObject()
