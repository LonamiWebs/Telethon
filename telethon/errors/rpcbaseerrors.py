from ..tl import functions

_NESTS_QUERY = (
    functions.InvokeAfterMsgRequest,
    functions.InvokeAfterMsgsRequest,
    functions.InitConnectionRequest,
    functions.InvokeWithLayerRequest,
    functions.InvokeWithoutUpdatesRequest,
    functions.InvokeWithMessagesRangeRequest,
    functions.InvokeWithTakeoutRequest,
)

class RPCError(Exception):
    """Base class for all Remote Procedure Call errors."""
    code = None
    message = None

    def __init__(self, request, message, code=None):
        super().__init__('RPCError {}: {}{}'.format(
            code or self.code, message, self._fmt_request(request)))

        self.request = request
        self.code = code
        self.message = message

    @staticmethod
    def _fmt_request(request):
        n = 0
        reason = ''
        while isinstance(request, _NESTS_QUERY):
            n += 1
            reason += request.__class__.__name__ + '('
            request = request.query
        reason += request.__class__.__name__ + ')' * n

        return ' (caused by {})'.format(reason)

    def __reduce__(self):
        return type(self), (self.request, self.message, self.code)


class InvalidDCError(RPCError):
    """
    The request must be repeated, but directed to a different data center.
    """
    code = 303
    message = 'ERROR_SEE_OTHER'


class BadRequestError(RPCError):
    """
    The query contains errors. In the event that a request was created
    using a form and contains user generated data, the user should be
    notified that the data must be corrected before the query is repeated.
    """
    code = 400
    message = 'BAD_REQUEST'


class UnauthorizedError(RPCError):
    """
    There was an unauthorized attempt to use functionality available only
    to authorized users.
    """
    code = 401
    message = 'UNAUTHORIZED'


class ForbiddenError(RPCError):
    """
    Privacy violation. For example, an attempt to write a message to
    someone who has blacklisted the current user.
    """
    code = 403
    message = 'FORBIDDEN'


class NotFoundError(RPCError):
    """
    An attempt to invoke a non-existent object, such as a method.
    """
    code = 404
    message = 'NOT_FOUND'


class AuthKeyError(RPCError):
    """
    Errors related to invalid authorization key, like
    AUTH_KEY_DUPLICATED which can cause the connection to fail.
    """
    code = 406
    message = 'AUTH_KEY'


class FloodError(RPCError):
    """
    The maximum allowed number of attempts to invoke the given method
    with the given input parameters has been exceeded. For example, in an
    attempt to request a large number of text messages (SMS) for the same
    phone number.
    """
    code = 420
    message = 'FLOOD'


class ServerError(RPCError):
    """
    An internal server error occurred while a request was being processed
    for example, there was a disruption while accessing a database or file
    storage.
    """
    code = 500  # Also witnessed as -500
    message = 'INTERNAL'


class TimedOutError(RPCError):
    """
    Clicking the inline buttons of bots that never (or take to long to)
    call ``answerCallbackQuery`` will result in this "special" RPCError.
    """
    code = 503  # Only witnessed as -503
    message = 'Timeout'


BotTimeout = TimedOutError


base_errors = {x.code: x for x in (
    InvalidDCError, BadRequestError, UnauthorizedError, ForbiddenError,
    NotFoundError, AuthKeyError, FloodError, ServerError, TimedOutError
)}
