"""Errors not related to the Telegram API itself"""


class ReadCancelledError(Exception):
    """Occurs when a read operation was cancelled"""
    def __init__(self):
        super().__init__(self, 'The read operation was cancelled.')


class InvalidParameterError(Exception):
    """Occurs when an invalid parameter is given, for example,
    when either A or B are required but none is given"""


class TypeNotFoundError(Exception):
    """Occurs when a type is not found, for example,
    when trying to read a TLObject with an invalid constructor code"""

    def __init__(self, invalid_constructor_id):
        super().__init__(
            self, 'Could not find a matching Constructor ID for the TLObject '
            'that was supposed to be read with ID {}. Most likely, a TLObject '
            'was trying to be read when it should not be read.'
            .format(hex(invalid_constructor_id)))

        self.invalid_constructor_id = invalid_constructor_id


class InvalidChecksumError(Exception):
    def __init__(self, checksum, valid_checksum):
        super().__init__(
            self,
            'Invalid checksum ({} when {} was expected). This packet should be skipped.'
            .format(checksum, valid_checksum))

        self.checksum = checksum
        self.valid_checksum = valid_checksum
