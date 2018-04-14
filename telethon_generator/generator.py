from telethon_generator.parsers import parse_errors, parse_tl, find_layer
from telethon_generator.generators import generate_errors, generate_tlobjects


ERRORS_INPUT_JSON = 'errors.json'
ERRORS_INPUT_DESC = 'error_descriptions'
ERRORS_OUTPUT = '../telethon/errors/rpc_error_list.py'

TLOBJECT_INPUT_TL = 'scheme.tl'
TLOBJECT_OUTPUT = '../telethon/tl'


if __name__ == '__main__':
    generate_tlobjects(
        tlobjects=list(parse_tl(TLOBJECT_INPUT_TL, ignore_core=True)),
        layer=find_layer((TLOBJECT_INPUT_TL)),
        output_dir=TLOBJECT_OUTPUT
    )

    with open(ERRORS_OUTPUT, 'w', encoding='utf-8') as file:
        generate_errors(
            errors=list(parse_errors(ERRORS_INPUT_JSON, ERRORS_INPUT_DESC)),
            f=file
        )
