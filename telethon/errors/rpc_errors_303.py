from . import InvalidDCError


class FileMigrateError(InvalidDCError):
    def __init__(self, **kwargs):
        self.new_dc = kwargs['extra']
        super(Exception, self).__init__(
            self,
            'The file to be accessed is currently stored in DC {}.'
            .format(self.new_dc)
        )


class PhoneMigrateError(InvalidDCError):
    def __init__(self, **kwargs):
        self.new_dc = kwargs['extra']
        super(Exception, self).__init__(
            self,
            'The phone number a user is trying to use for authorization is '
            'associated with DC {}.'
            .format(self.new_dc)
        )


class NetworkMigrateError(InvalidDCError):
    def __init__(self, **kwargs):
        self.new_dc = kwargs['extra']
        super(Exception, self).__init__(
            self,
            'The source IP address is associated with DC {}.'
            .format(self.new_dc)
        )


class UserMigrateError(InvalidDCError):
    def __init__(self, **kwargs):
        self.new_dc = kwargs['extra']
        super(Exception, self).__init__(
            self,
            'The user whose identity is being used to execute queries is '
            'associated with DC {}.'
            .format(self.new_dc)
        )


rpc_303_errors = {
    'FILE_MIGRATE_(\d+)': FileMigrateError,
    'PHONE_MIGRATE_(\d+)': PhoneMigrateError,
    'NETWORK_MIGRATE_(\d+)': NetworkMigrateError,
    'USER_MIGRATE_(\d+)': UserMigrateError
}
