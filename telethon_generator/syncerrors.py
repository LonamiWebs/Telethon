# Should be fed with the JSON obtained from https://core.telegram.org/api/errors#error-database
import re
import csv
import sys
import json
from pathlib import Path

sys.path.insert(0, '..')

from telethon_generator.parsers.errors import parse_errors, Error
from telethon_generator.parsers.methods import parse_methods, MethodInfo

ERRORS = Path('data/errors.csv')
METHODS = Path('data/methods.csv')
FRIENDLY = Path('data/friendly.csv')


def main():
    new_errors = []
    new_methods = []

    self_errors = {e.str_code: e for e in parse_errors(ERRORS)}
    self_methods = {m.name: m for m in parse_methods(METHODS, FRIENDLY, self_errors)}

    tg_data = json.load(sys.stdin)

    def get_desc(code):
        return re.sub(r'\s*&\w+;\s*', '', (tg_data['descriptions'].get(code) or '').rstrip('.'))

    for int_code, errors in tg_data['errors'].items():
        int_code = int(int_code)  # json does not support non-string keys
        for code, methods in errors.items():
            if not re.match(r'\w+', code):
                continue  # skip, full code is unknown (contains asterisk or is multiple words)
            str_code = code.replace('%d', 'X')
            if error := self_errors.get(str_code):
                error.int_codes.append(int_code)  # de-duplicated once later
                if not error.description:  # prefer our descriptions
                    if not error.has_captures:  # need descriptions with specific text if error has captures
                        error.description = get_desc(code)
            else:
                self_errors[str_code] = Error([int_code], str_code, get_desc(code))

    new_errors.extend((e.str_code, ' '.join(map(str, sorted(set(e.int_codes)))), e.description) for e in self_errors.values())
    new_methods.extend((m.name, m.usability.key, ' '.join(sorted(e.str_code for e in m.errors))) for m in self_methods.values())

    csv.register_dialect('plain', lineterminator='\n')
    with ERRORS.open('w', encoding='utf-8', newline='') as fd:
        csv.writer(fd, 'plain').writerows((('name', 'codes', 'description'), *sorted(new_errors)))
    with METHODS.open('w', encoding='utf-8', newline='') as fd:
        csv.writer(fd, 'plain').writerows((('method', 'usability', 'errors'), *sorted(new_methods)))


if __name__ == '__main__':
    main()
