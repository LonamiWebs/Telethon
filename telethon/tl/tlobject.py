from threading import Event


class TLObject:
    def __init__(self):
        self.request_msg_id = 0  # Long

        self.confirm_received = Event()
        self.rpc_error = None

        # These should be overrode
        self.constructor_id = 0
        self.content_related = False  # Only requests/functions/queries are

    # These should not be overrode
    @staticmethod
    def pretty_format(obj, indent=None):
        """Pretty formats the given object as a string which is returned.
           If indent is None, a single line will be returned.
        """
        if indent is None:
            if isinstance(obj, TLObject):
                return '{{{}: {}}}'.format(
                    type(obj).__name__,
                    TLObject.pretty_format(obj.to_dict())
                )
            if isinstance(obj, dict):
                return '{{{}}}'.format(', '.join(
                    '{}: {}'.format(
                        k, TLObject.pretty_format(v)
                    ) for k, v in obj.items()
                ))
            elif isinstance(obj, str) or isinstance(obj, bytes):
                return repr(obj)
            elif hasattr(obj, '__iter__'):
                return '[{}]'.format(
                    ', '.join(TLObject.pretty_format(x) for x in obj)
                )
            else:
                return str(obj)
        else:
            result = []
            if isinstance(obj, TLObject):
                result.append('{')
                result.append(type(obj).__name__)
                result.append(': ')
                result.append(TLObject.pretty_format(
                    obj.to_dict(), indent
                ))

            elif isinstance(obj, dict):
                result.append('{\n')
                indent += 1
                for k, v in obj.items():
                    result.append('\t' * indent)
                    result.append(k)
                    result.append(': ')
                    result.append(TLObject.pretty_format(v, indent))
                    result.append(',\n')
                indent -= 1
                result.append('\t' * indent)
                result.append('}')

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
                result.append(str(obj))

            return ''.join(result)

    # These should be overrode
    def to_dict(self):
        return {}

    def on_send(self, writer):
        pass

    def on_response(self, reader):
        pass
