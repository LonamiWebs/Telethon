import csv
import enum


class Usability(enum.Enum):
    UNKNOWN = 0
    USER = 1
    BOT = 2
    BOTH = 4


class MethodInfo:
    def __init__(self, name, usability, errors):
        self.name = name
        self.errors = errors
        try:
            self.usability = {
                'unknown': Usability.UNKNOWN,
                'user': Usability.USER,
                'bot': Usability.BOT,
                'both': Usability.BOTH,
            }[usability.lower()]
        except KeyError:
            raise ValueError('Usability must be either user, bot, both or '
                             'unknown, not {}'.format(usability)) from None


def parse_methods(csv_file, errors_dict):
    """
    Parses the input CSV file with columns (method, usability, errors)
    and yields `MethodInfo` instances as a result.
    """
    with open(csv_file, newline='') as f:
        f = csv.reader(f)
        next(f, None)  # header
        for line, (method, usability, errors) in enumerate(f, start=2):
            try:
                errors = [errors_dict[x] for x in errors.split()]
            except KeyError:
                raise ValueError('Method {} references unknown errors {}'
                                 .format(method, errors)) from None

            yield MethodInfo(method, usability, errors)
