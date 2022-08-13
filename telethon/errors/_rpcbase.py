import re

from ._generated import _captures, _descriptions
from .. import _tl


_NESTS_QUERY = (
    _tl.fn.InvokeAfterMsg,
    _tl.fn.InvokeAfterMsgs,
    _tl.fn.InitConnection,
    _tl.fn.InvokeWithLayer,
    _tl.fn.InvokeWithoutUpdates,
    _tl.fn.InvokeWithMessagesRange,
    _tl.fn.InvokeWithTakeout,
)


class RpcError(Exception):
    def __init__(self, code, message, request=None):
        # Special-case '2fa' to exclude the 2 from values
        self.values = [int(x) for x in re.findall(r'-?\d+', re.sub(r'^2fa', '', message, flags=re.IGNORECASE))]
        self.value = self.values[0] if self.values else None

        doc = self.__doc__
        if doc is None:
            doc = (
                '\n    Please report this error at https://github.com/LonamiWebs/Telethon/issues/3169'
                '\n    (the library is not aware of it yet and we would appreciate your help, thank you!)'
            )
        elif not doc:
            doc = '(no description available)'
        elif self.value:
            doc = re.sub(r'{(\w+)}', str(self.value), doc)

        super().__init__(f'{message}, code={code}{self._fmt_request(request)}: {doc}')
        self.code = code
        self.message = message
        self.request = request

    @staticmethod
    def _fmt_request(request):
        if not request:
            return ''

        n = 0
        reason = ''
        while isinstance(request, _NESTS_QUERY):
            n += 1
            reason += request.__class__.__name__ + '('
            request = request.query
        reason += request.__class__.__name__ + ')' * n

        return ', request={}'.format(reason)

    def __reduce__(self):
        return type(self), (self.request, self.message, self.code)


def _mk_error_type(*, name=None, code=None, doc=None, _errors={}) -> type:
    if name is None and code is None:
        raise ValueError('at least one of `name` or `code` must be provided')

    if name is not None:
        # Special-case '2fa' to 'twofa'
        name = re.sub(r'^2fa', 'twofa', name, flags=re.IGNORECASE)

        # Get canonical name
        name = re.sub(r'[-_\d]', '', name).lower()
        while name.endswith('error'):
            name = name[:-len('error')]

        doc = _descriptions.get(name, doc)
        capture_alias = _captures.get(name)

        d = {'__doc__': doc}

        if capture_alias:
            d[capture_alias] = property(
                fget=lambda s: s.value,
                doc='Alias for `self.value`. Useful to make the code easier to follow.'
            )

        if (name, None) not in _errors:
            _errors[(name, None)] = type(f'RpcError{name.title()}', (RpcError,), d)

    if code is not None:
        # Pretend negative error codes are positive
        code = str(abs(code))
        if (None, code) not in _errors:
            _errors[(None, code)] = type(f'RpcError{code}', (RpcError,), {'__doc__': doc})

    if (name, code) not in _errors:
        specific = _errors[(name, None)]
        base = _errors[(None, code)]
        _errors[(name, code)] = type(f'RpcError{name.title()}{code}', (specific, base), {'__doc__': doc})

    return _errors[(name, code)]


InvalidDcError = _mk_error_type(code=303, doc="""
    The request must be repeated, but directed to a different data center.
""")

BadRequestError = _mk_error_type(code=400, doc="""
    The query contains errors. In the event that a request was created
    using a form and contains user generated data, the user should be
    notified that the data must be corrected before the query is repeated.
""")

UnauthorizedError = _mk_error_type(code=401, doc="""
    There was an unauthorized attempt to use functionality available only
    to authorized users.
""")

ForbiddenError = _mk_error_type(code=403, doc="""
    Privacy violation. For example, an attempt to write a message to
    someone who has blacklisted the current user.
""")

NotFoundError = _mk_error_type(code=404, doc="""
    An attempt to invoke a non-existent object, such as a method.
""")

AuthKeyError = _mk_error_type(code=406, doc="""
    Errors related to invalid authorization key, like
    AUTH_KEY_DUPLICATED which can cause the connection to fail.
""")

FloodError = _mk_error_type(code=420, doc="""
    The maximum allowed number of attempts to invoke the given method
    with the given input parameters has been exceeded. For example, in an
    attempt to request a large number of text messages (SMS) for the same
    phone number.
""")

# Witnessed as -500 for "No workers running"
ServerError = _mk_error_type(code=500, doc="""
    An internal server error occurred while a request was being processed
    for example, there was a disruption while accessing a database or file
    storage.
""")

# Witnessed as -503 for "Timeout"
BotTimeout = TimedOutError = _mk_error_type(code=503, doc="""
    Clicking the inline buttons of bots that never (or take to long to)
    call ``answerCallbackQuery`` will result in this "special" RpcError.
""")
