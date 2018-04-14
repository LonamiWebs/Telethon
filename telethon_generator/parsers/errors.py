import json
from collections import defaultdict

import re

# Core base classes depending on the integer error code
KNOWN_BASE_CLASSES = {
    303: 'InvalidDCError',
    400: 'BadRequestError',
    401: 'UnauthorizedError',
    403: 'ForbiddenError',
    404: 'NotFoundError',
    406: 'AuthKeyError',
    420: 'FloodError',
    500: 'ServerError',
}

# The API doesn't return the code for some (vital) errors. They are
# all assumed to be 400, except these well-known ones that aren't.
KNOWN_CODES = {
    'ACTIVE_USER_REQUIRED': 401,
    'AUTH_KEY_UNREGISTERED': 401,
    'USER_DEACTIVATED': 401
}

# Give better semantic names to some captures
CAPTURE_NAMES = {
    'FloodWaitError': 'seconds',
    'FloodTestPhoneWaitError': 'seconds',
    'FileMigrateError': 'new_dc',
    'NetworkMigrateError': 'new_dc',
    'PhoneMigrateError': 'new_dc',
    'UserMigrateError': 'new_dc',
    'FilePartMissingError': 'which'
}


def _get_class_name(error_code):
    """
    Gets the corresponding class name for the given error code,
    this either being an integer (thus base error name) or str.
    """
    if isinstance(error_code, int):
        return KNOWN_BASE_CLASSES.get(
            error_code, 'RPCError' + str(error_code).replace('-', 'Neg')
        )

    if 'FIRSTNAME' in error_code:
        error_code = error_code.replace('FIRSTNAME', 'FIRST_NAME')

    result = re.sub(
        r'_([a-z])', lambda m: m.group(1).upper(), error_code.lower()
    )
    return result[:1].upper() + result[1:].replace('_', '') + 'Error'


class Error:
    def __init__(self, int_code, str_code, description):
        # TODO Some errors have the same str_code but different int_code
        # Should these be split into different files or doesn't really matter?
        # Telegram isn't exactly consistent with returned errors anyway.
        self.int_code = int_code
        self.str_code = str_code
        self.subclass = _get_class_name(int_code)
        self.subclass_exists = int_code in KNOWN_BASE_CLASSES
        self.description = description

        self.has_captures = '_X' in str_code
        if self.has_captures:
            self.name = _get_class_name(str_code.replace('_X', ''))
            self.pattern = str_code.replace('_X', r'_(\d+)')
            self.capture_name = CAPTURE_NAMES.get(self.name, 'x')
        else:
            self.name = _get_class_name(str_code)
            self.pattern = str_code
            self.capture_name = None


def parse_errors(json_file, descriptions_file):
    """
    Parses the given JSON file in the following format:
        {
            "ok": true,
            "human_result": {"int_code": ["descriptions"]},
            "result": {"int_code": {"full_method_name": ["str_error"]}}
        }

    The descriptions file, which has precedence over the JSON's human_result,
    should have the following format:
        # comment
        str_error=Description

    The method yields `Error` instances as a result.
    """
    with open(json_file, encoding='utf-8') as f:
        data = json.load(f)

    errors = defaultdict(set)
    # PWRTelegram's API doesn't return all errors, which we do need here.
    # Add some special known-cases manually first.
    errors[420].update((
        'FLOOD_WAIT_X', 'FLOOD_TEST_PHONE_WAIT_X'
    ))
    errors[401].update((
        'AUTH_KEY_INVALID', 'SESSION_EXPIRED', 'SESSION_REVOKED'
    ))
    errors[303].update((
        'FILE_MIGRATE_X', 'PHONE_MIGRATE_X',
        'NETWORK_MIGRATE_X', 'USER_MIGRATE_X'
    ))
    for int_code, method_errors in data['result'].items():
        for error_list in method_errors.values():
            for error in error_list:
                errors[int(int_code)].add(re.sub('_\d+', '_X', error).upper())

    # Some errors are in the human result, but not with a code. Assume 400
    for error in data['human_result']:
        if error[0] != '-' and not error.isdigit():
            error = re.sub('_\d+', '_X', error).upper()
            if not any(error in es for es in errors.values()):
                errors[KNOWN_CODES.get(error, 400)].add(error)

    # Prefer the descriptions that are related with Telethon way of coding
    # to those that PWRTelegram's API provides.
    telethon_descriptions = {}
    with open(descriptions_file, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                equal = line.index('=')
                message, description = line[:equal], line[equal + 1:]
                telethon_descriptions[message.rstrip()] = description.lstrip()

    for int_code, error_set in errors.items():
        for str_code in sorted(error_set):
            description = telethon_descriptions.get(
                str_code, '\n'.join(data['human_result'].get(
                    str_code, ['No description known.']
                ))
            )
            yield Error(
                int_code=int_code,
                str_code=str_code,
                description=description,
            )
