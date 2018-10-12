"""Errors not related to the Telegram API itself"""
import struct

from ..tl import TLRequest


class ReadCancelledError(Exception):
    """Occurs when a read operation was cancelled."""
    def __init__(self):
        super().__init__('The read operation was cancelled.')


class TypeNotFoundError(Exception):
    """
    Occurs when a type is not found, for example,
    when trying to read a TLObject with an invalid constructor code.
    """
    def __init__(self, invalid_constructor_id, remaining):
        super().__init__(
            'Could not find a matching Constructor ID for the TLObject '
            'that was supposed to be read with ID {:08x}. Most likely, '
            'a TLObject was trying to be read when it should not be read. '
            'Remaining bytes: {!r}'.format(invalid_constructor_id, remaining))

        self.invalid_constructor_id = invalid_constructor_id
        self.remaining = remaining


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


class InvalidBufferError(BufferError):
    """
    Occurs when the buffer is invalid, and may contain an HTTP error code.
    For instance, 404 means "forgotten/broken authorization key", while
    """
    def __init__(self, payload):
        self.payload = payload
        if len(payload) == 4:
            self.code = -struct.unpack('<i', payload)[0]
            super().__init__(
                'Invalid response buffer (HTTP code {})'.format(self.code))
        else:
            self.code = None
            super().__init__(
                'Invalid response buffer (too short {})'.format(self.payload))


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


class AlreadyInConversationError(Exception):
    """
    Occurs when another exclusive conversation is opened in the same chat.
    """
    def __init__(self):
        super().__init__(
            'Cannot open exclusive conversation in a '
            'chat that already has one open conversation'
        )


class MultiError(Exception):
    """Exception container for multiple `TLRequest`'s."""

    def __new__(cls, exceptions, result, requests):
        if len(result) != len(exceptions) != len(requests):
            raise ValueError(
                'Need result, exception and request for each error')
        for e, req in zip(exceptions, requests):
            if not isinstance(e, BaseException) and e is not None:
                raise TypeError(
                    "Expected an exception object, not '%r'" % e
                )
            if not isinstance(req, TLRequest):
                raise TypeError(
                    "Expected TLRequest object, not '%r'" % req
                )

        if len(exceptions) == 1:
            return exceptions[0]
        self = BaseException.__new__(cls)
        self.exceptions = list(exceptions)
        self.results = list(result)
        self.requests = list(requests)
        return self
