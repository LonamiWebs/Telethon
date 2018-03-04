"""Errors not related to the Telegram API itself"""


class ReadCancelledError(Exception):
    """Occurs when a read operation was cancelled."""
    def __init__(self):
        super().__init__('The read operation was cancelled.')


class TypeNotFoundError(Exception):
    """
    Occurs when a type is not found, for example,
    when trying to read a TLObject with an invalid constructor code.
    """
    def __init__(self, invalid_constructor_id):
        super().__init__(
            'Could not find a matching Constructor ID for the TLObject '
            'that was supposed to be read with ID {}. Most likely, a TLObject '
            'was trying to be read when it should not be read.'
            .format(hex(invalid_constructor_id)))

        self.invalid_constructor_id = invalid_constructor_id


class InvalidChecksumError(Exception):
    """
    Occurs when using the TCP full mode and the checksum of a received
    packet doesn't match the expected checksum.
    """
    def __init__(self, checksum, valid_checksum):
        super().__init__(
            'Invalid checksum ({} when {} was expected). '
            'This packet should be skipped.'
            .format(checksum, valid_checksum))

        self.checksum = checksum
        self.valid_checksum = valid_checksum


class BrokenAuthKeyError(Exception):
    """
    Occurs when the authorization key for a data center is not valid.
    """
    def __init__(self):
        super().__init__(
            'The authorization key is broken, and it must be reset.'
        )


class SecurityError(Exception):
    """
    Generic security error, mostly used when generating a new AuthKey.
    """
    def __init__(self, *args):
        if not args:
            args = ['A security check failed.']
        super().__init__(*args)


class CdnFileTamperedError(SecurityError):
    """
    Occurs when there's a hash mismatch between the decrypted CDN file
    and its expected hash.
    """
    def __init__(self):
        super().__init__(
            'The CDN file has been altered and its download cancelled.'
        )
