import json
import re
import urllib.request
from collections import defaultdict

URL = 'https://rpc.pwrtelegram.xyz/?all'

known_base_classes = {
    303: 'InvalidDCError',
    400: 'BadRequestError',
    401: 'UnauthorizedError',
    403: 'ForbiddenError',
    404: 'NotFoundError',
    420: 'FloodError',
    500: 'ServerError',
}

# The API doesn't return the code for some (vital) errors. They are
# all assumed to be 400, except these well-known ones that aren't.
known_codes = {
    'ACTIVE_USER_REQUIRED': 401,
    'AUTH_KEY_UNREGISTERED': 401,
    'USER_DEACTIVATED': 401
}


def fetch_errors(output, url=URL):
    print('Opening a connection to', url, '...')
    r = urllib.request.urlopen(urllib.request.Request(
        url, headers={'User-Agent' : 'Mozilla/5.0'}
    ))
    print('Checking response...')
    data = json.loads(
        r.read().decode(r.info().get_param('charset') or 'utf-8')
    )
    if data.get('ok'):
        print('Response was okay, saving data')
        with open(output, 'w', encoding='utf-8') as f:
            json.dump(data, f, sort_keys=True)
        return True
    else:
        print('The data received was not okay:')
        print(json.dumps(data, indent=4, sort_keys=True))
        return False


def get_class_name(error_code):
    if isinstance(error_code, int):
        return known_base_classes.get(
            error_code, 'RPCError' + str(error_code).replace('-', 'Neg')
        )

    if 'FIRSTNAME' in error_code:
        error_code = error_code.replace('FIRSTNAME', 'FIRST_NAME')

    result = re.sub(
        r'_([a-z])', lambda m: m.group(1).upper(), error_code.lower()
    )
    return result[:1].upper() + result[1:].replace('_', '') + 'Error'


def write_error(f, code, name, desc, capture_name):
    f.write(
        '\n\nclass {}({}):\n    def __init__(self, **kwargs):\n        '
        ''.format(name, get_class_name(code))
    )
    if capture_name:
        f.write(
            "self.{} = int(kwargs.get('capture', 0))\n        ".format(capture_name)
        )
    f.write('super(Exception, self).__init__({}'.format(repr(desc)))
    if capture_name:
        f.write('.format(self.{})'.format(capture_name))
    f.write(')\n')


def generate_code(output, json_file, errors_desc):
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
    for error_code, method_errors in data['result'].items():
        for error_list in method_errors.values():
            for error in error_list:
                errors[int(error_code)].add(re.sub('_\d+', '_X', error).upper())

    # Some errors are in the human result, but not with a code. Assume code 400
    for error in data['human_result']:
        if error[0] != '-' and not error.isdigit():
            error = re.sub('_\d+', '_X', error).upper()
            if not any(error in es for es in errors.values()):
                errors[known_codes.get(error, 400)].add(error)

    # Some error codes are not known, so create custom base classes if needed
    needed_base_classes = [
        (e, get_class_name(e)) for e in errors if e not in known_base_classes
    ]

    # Prefer the descriptions that are related with Telethon way of coding to
    # those that PWRTelegram's API provides.
    telethon_descriptions = {}
    with open(errors_desc, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                equal = line.index('=')
                message, description = line[:equal], line[equal + 1:]
                telethon_descriptions[message.rstrip()] = description.lstrip()

    # Names for the captures, or 'x' if unknown
    capture_names = {
        'FloodWaitError': 'seconds',
        'FloodTestPhoneWaitError': 'seconds',
        'FileMigrateError': 'new_dc',
        'NetworkMigrateError': 'new_dc',
        'PhoneMigrateError': 'new_dc',
        'UserMigrateError': 'new_dc',
        'FilePartMissingError': 'which'
    }

    # Everything ready, generate the code
    with open(output, 'w', encoding='utf-8') as f:
        f.write(
            'from .rpc_base_errors import RPCError, BadMessageError, {}\n'.format(
                ", ".join(known_base_classes.values()))
        )
        for code, cls in needed_base_classes:
            f.write(
                '\n\nclass {}(RPCError):\n    code = {}\n'.format(cls, code)
            )

        patterns = []  # Save this dictionary later in the generated code
        for error_code, error_set in errors.items():
            for error in sorted(error_set):
                description = telethon_descriptions.get(
                    error, '\n'.join(data['human_result'].get(
                        error, ['No description known.']
                    ))
                )
                has_captures = '_X' in error
                if has_captures:
                    name = get_class_name(error.replace('_X', ''))
                    pattern = error.replace('_X', r'_(\d+)')
                else:
                    name, pattern = get_class_name(error), error

                patterns.append((pattern, name))
                capture = capture_names.get(name, 'x') if has_captures else None
                # TODO Some errors have the same name but different code,
                # split this across different files?
                write_error(f, error_code, name, description, capture)

        f.write('\n\nrpc_errors_all = {\n')
        for pattern, name in patterns:
            f.write('    {}: {},\n'.format(repr(pattern), name))
        f.write('}\n')


if __name__ == '__main__':
    if input('generate (y/n)?: ').lower() == 'y':
        generate_code('../telethon/errors/rpc_error_list.py',
                      'errors.json', 'error_descriptions')
    elif input('fetch (y/n)?: ').lower() == 'y':
        fetch_errors('errors.json')
