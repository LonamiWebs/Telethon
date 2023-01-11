import csv
import enum
import warnings


class Usability(enum.Enum):
    UNKNOWN = 0
    USER = 1
    BOT = 2
    BOTH = 4

    @property
    def key(self):
        return {
            Usability.UNKNOWN: 'unknown',
            Usability.USER: 'user',
            Usability.BOT: 'bot',
            Usability.BOTH: 'both',
        }[self]


class MethodInfo:
    def __init__(self, name, usability, errors, friendly):
        self.name = name
        self.errors = errors
        self.friendly = friendly
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


def parse_methods(csv_file, friendly_csv_file, errors_dict):
    """
    Parses the input CSV file with columns (method, usability, errors)
    and yields `MethodInfo` instances as a result.
    """
    raw_to_friendly = {}
    with friendly_csv_file.open(newline='') as f:
        f = csv.reader(f)
        next(f, None)  # header
        for ns, friendly, raw_list in f:
            for raw in raw_list.split():
                raw_to_friendly[raw] = (ns, friendly)

    with csv_file.open(newline='') as f:
        f = csv.reader(f)
        next(f, None)  # header
        for line, (method, usability, errors) in enumerate(f, start=2):
            try:
                errors = [errors_dict[x] for x in errors.split()]
            except KeyError:
                raise ValueError('Method {} references unknown errors {}'
                                 .format(method, errors)) from None

            friendly = raw_to_friendly.pop(method, None)
            yield MethodInfo(method, usability, errors, friendly)

    if raw_to_friendly:
        warnings.warn('note: unknown raw methods in friendly mapping: {}'
                      .format(', '.join(raw_to_friendly)))
