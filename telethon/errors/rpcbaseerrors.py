class RPCError(Exception):
    """Base class for all Remote Procedure Call errors."""
    code = None
    message = None

    def __init__(self, message, code=None):
        super().__init__('RPCError {}: {}'.format(code or self.code, message))
        self.code = code
        self.message = message

    def __reduce__(self):
        return type(self), (self.code, self.message)


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

    def __init__(self, message):
        super().__init__(message)
        self.message = message


class NotFoundError(RPCError):
    """
    An attempt to invoke a non-existent object, such as a method.
    """
    code = 404
    message = 'NOT_FOUND'

    def __init__(self, message):
        super().__init__(message)
        self.message = message


class AuthKeyError(RPCError):
    """
    Errors related to invalid authorization key, like
    AUTH_KEY_DUPLICATED which can cause the connection to fail.
    """
    code = 406
    message = 'AUTH_KEY'

    def __init__(self, message):
        super().__init__(message)
        self.message = message


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
    code = 500
    message = 'INTERNAL'

    def __init__(self, message):
        super().__init__(message)
        self.message = message


class BotTimeout(RPCError):
    """
    Clicking the inline buttons of bots that never (or take to long to)
    call ``answerCallbackQuery`` will result in this "special" RPCError.
    """
    code = -503
    message = 'Timeout'

    def __init__(self, message):
        super().__init__(message)
        self.message = message


class BadMessageError(Exception):
    """Occurs when handling a bad_message_notification."""
    ErrorMessages = {
        16:
        'msg_id too low (most likely, client time is wrong it would be '
        'worthwhile to synchronize it using msg_id notifications and re-send '
        'the original message with the "correct" msg_id or wrap it in a '
        'container with a new msg_id if the original message had waited too '
        'long on the client to be transmitted).',
        17:
        'msg_id too high (similar to the previous case, the client time has '
        'to be synchronized, and the message re-sent with the correct msg_id).',
        18:
        'Incorrect two lower order msg_id bits (the server expects client '
        'message msg_id to be divisible by 4).',
        19:
        'Container msg_id is the same as msg_id of a previously received '
        'message (this must never happen).',
        20:
        'Message too old, and it cannot be verified whether the server has '
        'received a message with this msg_id or not.',
        32:
        'msg_seqno too low (the server has already received a message with a '
        'lower msg_id but with either a higher or an equal and odd seqno).',
        33:
        'msg_seqno too high (similarly, there is a message with a higher '
        'msg_id but with either a lower or an equal and odd seqno).',
        34:
        'An even msg_seqno expected (irrelevant message), but odd received.',
        35:
        'Odd msg_seqno expected (relevant message), but even received.',
        48:
        'Incorrect server salt (in this case, the bad_server_salt response '
        'is received with the correct salt, and the message is to be re-sent '
        'with it).',
        64:
        'Invalid container.'
    }

    def __init__(self, code):
        super().__init__(self.ErrorMessages.get(
            code,
            'Unknown error code (this should not happen): {}.'.format(code)))

        self.code = code


base_errors = {x.code: x for x in (
    InvalidDCError, BadRequestError, UnauthorizedError, ForbiddenError,
    NotFoundError, AuthKeyError, FloodError, ServerError, BotTimeout
)}
