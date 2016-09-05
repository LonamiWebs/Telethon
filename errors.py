class InvalidParameterError(Exception):
    """Occurs when an invalid parameter is given, for example,
    when either A or B are required but none is given"""


class TypeNotFoundError(Exception):
    """Occurs when a type is not found, for example,
    when trying to read a TLObject with an invalid constructor code"""
    def __init__(self, invalid_constructor_id):
        super().__init__(self, 'Could not find a matching Constructor ID for the TLObject '
                               'that was supposed to be read with ID {}. Most likely, a TLObject '
                               'was trying to be read when it should not be read.'
                               .format(hex(invalid_constructor_id)))

        self.invalid_constructor_id = invalid_constructor_id


class InvalidDCError(Exception):
    def __init__(self, new_dc):
        super().__init__(self,  'Your phone number is registered to #{} DC. '
                                'This should have been handled automatically; '
                                'if it has not, please restart the app.')

        self.new_dc = new_dc


class InvalidChecksumError(Exception):
    def __init__(self, checksum, valid_checksum):
        super().__init__(self,  'Invalid checksum ({} when {} was expected). This packet should be skipped.'
                                .format(checksum, valid_checksum))

        self.checksum = checksum
        self.valid_checksum = valid_checksum


class RPCError(Exception):
    def __init__(self, message):
        super().__init__(self, message)
        self.message = message


class BadMessageError(Exception):
    """Occurs when handling a bad_message_notification"""
    ErrorMessages = {
        16: 'msg_id too low (most likely, client time is wrong it would be worthwhile to '
            'synchronize it using msg_id notifications and re-send the original message '
            'with the “correct” msg_id or wrap it in a container with a new msg_id if the '
            'original message had waited too long on the client to be transmitted).',

        17: 'msg_id too high (similar to the previous case, the client time has to be '
            'synchronized, and the message re-sent with the correct msg_id).',

        18: 'Incorrect two lower order msg_id bits (the server expects client message msg_id '
            'to be divisible by 4).',

        19: 'Container msg_id is the same as msg_id of a previously received message '
            '(this must never happen).',

        20: 'Message too old, and it cannot be verified whether the server has received a '
            'message with this msg_id or not.',

        32: 'msg_seqno too low (the server has already received a message with a lower '
            'msg_id but with either a higher or an equal and odd seqno).',

        33: 'msg_seqno too high (similarly, there is a message with a higher msg_id but with '
            'either a lower or an equal and odd seqno).',

        34: 'An even msg_seqno expected (irrelevant message), but odd received.',

        35: 'Odd msg_seqno expected (relevant message), but even received.',

        48: 'Incorrect server salt (in this case, the bad_server_salt response is received with '
            'the correct salt, and the message is to be re-sent with it).',

        64: 'Invalid container.'
    }

    def __init__(self, code):
        super().__init__(self, BadMessageError
                         .ErrorMessages.get(code,'Unknown error code (this should not happen): {}.'.format(code)))

        self.code = code
