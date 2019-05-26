import collections
import re

from .tlarg import TLArg
from .tlobject import TLObject
from ..methods import Usability


CORE_TYPES = {
    0xbc799737,  # boolFalse#bc799737 = Bool;
    0x997275b5,  # boolTrue#997275b5 = Bool;
    0x3fedd339,  # true#3fedd339 = True;
    0xc4b9f9bb,  # error#c4b9f9bb code:int text:string = Error;
    0x56730bcc   # null#56730bcc = Null;
}

# Telegram Desktop (C++) doesn't care about string/bytes, and the .tl files
# don't either. However in Python we *do*, and we want to deal with bytes
# for the authorization key process, not UTF-8 strings (they won't be).
#
# Every type with an ID that's in here should get their attribute types
# with string being replaced with bytes.
AUTH_KEY_TYPES = {
    0x05162463,  # resPQ,
    0x83c95aec,  # p_q_inner_data
    0xa9f55f95,  # p_q_inner_data_dc
    0x3c6a84d4,  # p_q_inner_data_temp
    0x56fddf88,  # p_q_inner_data_temp_dc
    0xd0e8075c,  # server_DH_params_ok
    0xb5890dba,  # server_DH_inner_data
    0x6643b654,  # client_DH_inner_data
    0xd712e4be,  # req_DH_params
    0xf5045f1f,  # set_client_DH_params
    0x3072cfa1   # gzip_packed
}


def _from_line(line, is_function, method_info, layer):
    match = re.match(
        r'^([\w.]+)'                     # 'name'
        r'(?:#([0-9a-fA-F]+))?'          # '#optionalcode'
        r'(?:\s{?\w+:[\w\d<>#.?!]+}?)*'  # '{args:.0?type}'
        r'\s=\s'                         # ' = '
        r'([\w\d<>#.?]+);$',             # '<result.type>;'
        line
    )
    if match is None:
        # Probably "vector#1cb5c415 {t:Type} # [ t ] = Vector t;"
        raise ValueError('Cannot parse TLObject {}'.format(line))

    args_match = re.findall(
        r'({)?'
        r'(\w+)'
        r':'
        r'([\w\d<>#.?!]+)'
        r'}?',
        line
    )

    name = match.group(1)
    method_info = method_info.get(name)
    if method_info:
        usability = method_info.usability
        friendly = method_info.friendly
    else:
        usability = Usability.UNKNOWN
        friendly = None

    return TLObject(
        fullname=name,
        object_id=match.group(2),
        result=match.group(3),
        is_function=is_function,
        layer=layer,
        usability=usability,
        friendly=friendly,
        args=[TLArg(name, arg_type, brace != '')
              for brace, name, arg_type in args_match]
    )


def parse_tl(file_path, layer, methods=None, ignored_ids=CORE_TYPES):
    """
    This method yields TLObjects from a given .tl file.

    Note that the file is parsed completely before the function yields
    because references to other objects may appear later in the file.
    """
    method_info = {m.name: m for m in (methods or [])}
    obj_all = []
    obj_by_name = {}
    obj_by_type = collections.defaultdict(list)
    with file_path.open() as file:
        is_function = False
        for line in file:
            comment_index = line.find('//')
            if comment_index != -1:
                line = line[:comment_index]

            line = line.strip()
            if not line:
                continue

            match = re.match(r'---(\w+)---', line)
            if match:
                following_types = match.group(1)
                is_function = following_types == 'functions'
                continue

            try:
                result = _from_line(
                    line, is_function, method_info, layer=layer)

                if result.id in ignored_ids:
                    continue

                obj_all.append(result)
                if not result.is_function:
                    obj_by_name[result.fullname] = result
                    obj_by_type[result.result].append(result)
            except ValueError as e:
                if 'vector#1cb5c415' not in str(e):
                    raise

    # Once all objects have been parsed, replace the
    # string type from the arguments with references
    for obj in obj_all:
        if obj.id in AUTH_KEY_TYPES:
            for arg in obj.args:
                if arg.type == 'string':
                    arg.type = 'bytes'

        for arg in obj.args:
            arg.cls = obj_by_type.get(arg.type) or (
                [obj_by_name[arg.type]] if arg.type in obj_by_name else []
            )

    yield from obj_all


def find_layer(file_path):
    """Finds the layer used on the specified scheme.tl file."""
    layer_regex = re.compile(r'^//\s*LAYER\s*(\d+)$')
    with file_path.open('r') as file:
        for line in file:
            match = layer_regex.match(line)
            if match:
                return int(match.group(1))
