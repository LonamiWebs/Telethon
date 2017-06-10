from . import UnauthorizedError


class ActiveUserRequiredError(UnauthorizedError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__(
            self,
            'The method is only available to already activated users.'
        )


class AuthKeyInvalidError(UnauthorizedError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__(
            self,
            'The key is invalid.'
        )


class AuthKeyPermEmptyError(UnauthorizedError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__(
            self,
            'The method is unavailable for temporary authorization key, not '
            'bound to permanent.'
        )


class AuthKeyUnregisteredError(UnauthorizedError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__(
            self,
            'The key is not registered in the system.'
        )


class InviteHashExpiredError(UnauthorizedError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__(
            self,
            'The chat the user tried to join has expired and is not valid '
            'anymore.'
        )


class SessionExpiredError(UnauthorizedError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__(
            self,
            'The authorization has expired.'
        )


class SessionPasswordNeededError(UnauthorizedError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__(
            self,
            'Two-steps verification is enabled and a password is required.'
        )


class SessionRevokedError(UnauthorizedError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__(
            self,
            'The authorization has been invalidated, because of the user '
            'terminating all sessions.'
        )


class UserAlreadyParticipantError(UnauthorizedError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__(
            self,
            'The authenticated user is already a participant of the chat.'
        )


class UserDeactivatedError(UnauthorizedError):
    def __init__(self, **kwargs):
        super(Exception, self).__init__(
            self,
            'The user has been deleted/deactivated.'
        )


rpc_401_errors = {
    'ACTIVE_USER_REQUIRED': ActiveUserRequiredError,
    'AUTH_KEY_INVALID': AuthKeyInvalidError,
    'AUTH_KEY_PERM_EMPTY': AuthKeyPermEmptyError,
    'AUTH_KEY_UNREGISTERED': AuthKeyUnregisteredError,
    'INVITE_HASH_EXPIRED': InviteHashExpiredError,
    'SESSION_EXPIRED': SessionExpiredError,
    'SESSION_PASSWORD_NEEDED': SessionPasswordNeededError,
    'SESSION_REVOKED': SessionRevokedError,
    'USER_ALREADY_PARTICIPANT': UserAlreadyParticipantError,
    'USER_DEACTIVATED': UserDeactivatedError,
}
