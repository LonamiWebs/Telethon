import csv
import re

from ..utils import snake_to_camel_case

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
    503: 'TimedOutError'
}


def _get_class_name(error_code):
    """
    Gets the corresponding class name for the given error code,
    this either being an integer (thus base error name) or str.
    """
    if isinstance(error_code, int):
        return KNOWN_BASE_CLASSES.get(
            abs(error_code), 'RPCError' + str(error_code).replace('-', 'Neg')
        )

    if error_code.startswith('2'):
        error_code = re.sub(r'2', 'TWO_', error_code, count=1)

    if re.match(r'\d+', error_code):
        raise RuntimeError('error code starting with a digit cannot have valid Python name: {}'.format(error_code))

    return snake_to_camel_case(
        error_code.replace('FIRSTNAME', 'FIRST_NAME')\
                  .replace('SLOWMODE', 'SLOW_MODE').lower(), suffix='Error')


class Error:
    def __init__(self, codes, name, description):
        # TODO Some errors have the same name but different integer codes
        # Should these be split into different files or doesn't really matter?
        # Telegram isn't exactly consistent with returned errors anyway.
        self.int_code = codes[0]
        self.str_code = name
        self.subclass = _get_class_name(codes[0])
        self.subclass_exists = abs(codes[0]) in KNOWN_BASE_CLASSES
        self.description = description

        self.has_captures = '_X' in name
        if self.has_captures:
            self.name = _get_class_name(name.replace('_X', '_'))
            self.pattern = name.replace('_X', r'_(\d+)')
            self.capture_name = re.search(r'{(\w+)}', description).group(1)
        else:
            self.name = _get_class_name(name)
            self.pattern = name
            self.capture_name = None


def parse_errors(csv_file):
    """
    Parses the input CSV file with columns (name, error codes, description)
    and yields `Error` instances as a result.
    """
    with csv_file.open(newline='') as f:
        f = csv.reader(f)
        next(f, None)  # header
        for line, tup in enumerate(f, start=2):
            try:
                name, codes, description = tup
            except ValueError:
                raise ValueError('Columns count mismatch, unquoted comma in '
                                 'desc? (line {})'.format(line)) from None

            try:
                codes = [int(x) for x in codes.split()] or [400]
            except ValueError:
                raise ValueError('Not all codes are integers '
                                 '(line {})'.format(line)) from None

            yield Error([int(x) for x in codes], name, description)
