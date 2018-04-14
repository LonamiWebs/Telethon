from telethon_generator.parsers import parse_errors
from telethon_generator.generators import generate_errors


INPUT_JSON = 'errors.json'
INPUT_DESCRIPTIONS = 'error_descriptions'
OUTPUT = '../telethon/errors/rpc_error_list.py'


if __name__ == '__main__':
    with open(OUTPUT, 'w', encoding='utf-8') as file:
        generate_errors(
            errors=list(parse_errors(INPUT_JSON, INPUT_DESCRIPTIONS)),
            f=file
        )
