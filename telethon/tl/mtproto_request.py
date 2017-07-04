from datetime import datetime, timedelta


class MTProtoRequest:
    def __init__(self):
        self.sent = False

        self.request_msg_id = 0  # Long
        self.sequence = 0

        self.dirty = False
        self.send_time = None
        self.confirm_received = False

        # These should be overrode
        self.constructor_id = 0
        self.confirmed = False
        self.responded = False

    # These should not be overrode
    def on_send_success(self):
        self.send_time = datetime.now()
        self.sent = True

    def on_confirm(self):
        self.confirm_received = True

    def need_resend(self):
        return self.dirty or (
            self.confirmed and not self.confirm_received and
            datetime.now() - self.send_time > timedelta(seconds=3))

    @staticmethod
    def pretty_format(obj, indent=None):
        """Pretty formats the given object as a string which is returned.
           If indent is None, a single line will be returned.
        """
        if indent is None:
            if isinstance(obj, MTProtoRequest):
                return '{{{}: {}}}'.format(
                    type(obj).__name__,
                    MTProtoRequest.pretty_format(obj.to_dict())
                )
            if isinstance(obj, dict):
                return '{{{}}}'.format(', '.join(
                    '{}: {}'.format(
                        k, MTProtoRequest.pretty_format(v)
                    ) for k, v in obj.items()
                ))
            elif isinstance(obj, str):
                return '"{}"'.format(obj)
            elif hasattr(obj, '__iter__'):
                return '[{}]'.format(
                    ', '.join(MTProtoRequest.pretty_format(x) for x in obj)
                )
            else:
                return str(obj)
        else:
            result = []
            if isinstance(obj, MTProtoRequest):
                result.append('{')
                result.append(type(obj).__name__)
                result.append(': ')
                result.append(MTProtoRequest.pretty_format(
                    obj.to_dict(), indent
                ))

            elif isinstance(obj, dict):
                result.append('{\n')
                indent += 1
                for k, v in obj.items():
                    result.append('\t' * indent)
                    result.append(k)
                    result.append(': ')
                    result.append(MTProtoRequest.pretty_format(v, indent))
                    result.append(',\n')
                indent -= 1
                result.append('\t' * indent)
                result.append('}')

            elif isinstance(obj, str):
                result.append('"')
                result.append(obj)
                result.append('"')

            elif hasattr(obj, '__iter__'):
                result.append('[\n')
                indent += 1
                for x in obj:
                    result.append('\t' * indent)
                    result.append(MTProtoRequest.pretty_format(x, indent))
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

    def on_exception(self, exception):
        pass
