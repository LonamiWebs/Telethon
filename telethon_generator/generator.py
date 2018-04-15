from telethon_generator.parsers import parse_errors, parse_tl, find_layer
from telethon_generator.generators import\
    generate_errors, generate_tlobjects, generate_docs


ERRORS_INPUT_JSON = 'data/errors.json'
ERRORS_INPUT_DESC = 'data/error_descriptions'
ERRORS_OUTPUT = '../telethon/errors/rpc_error_list.py'

TLOBJECT_INPUT_TL = 'data/scheme.tl'
TLOBJECT_OUTPUT = '../telethon/tl'

DOCS_INPUT_RES = 'data/html'
DOCS_OUTPUT = '../docs'


if __name__ == '__main__':
    tlobjects = list(parse_tl(TLOBJECT_INPUT_TL, ignore_core=True))
    errors = list(parse_errors(ERRORS_INPUT_JSON, ERRORS_INPUT_DESC))
    layer = find_layer(TLOBJECT_INPUT_TL)

    generate_tlobjects(tlobjects, layer, TLOBJECT_OUTPUT)
    with open(ERRORS_OUTPUT, 'w', encoding='utf-8') as file:
        generate_errors(errors, file)

    generate_docs(tlobjects, errors, layer, DOCS_INPUT_RES, DOCS_OUTPUT)
