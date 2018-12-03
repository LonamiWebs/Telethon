import collections
import re

from .tlarg import TLArg
from .tlobject import TLObject
from ..methods import Usability


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
    if name in method_info:
        usability = method_info[name].usability
    else:
        usability = Usability.UNKNOWN

    return TLObject(
        fullname=name,
        object_id=match.group(2),
        result=match.group(3),
        is_function=is_function,
        layer=layer,
        usability=usability,
        args=[TLArg(name, arg_type, brace != '')
              for brace, name, arg_type in args_match]
    )


def parse_tl(file_path, layer, methods=None):
    """
    This method yields TLObjects from a given .tl file.

    Note that the file is parsed completely before the function yields
    because references to other objects may appear later in the file.
    """
    method_info = {m.name: m for m in (methods or [])}
    obj_all = []
    obj_by_name = {}
    obj_by_type = collections.defaultdict(list)
    with open(file_path, 'r', encoding='utf-8') as file:
        is_function = False
        for line in file:
            comment_index = line.find('//')
            if comment_index != -1:
                line = line[:comment_index]

            line = line.strip()
            if not line:
                continue

            match = re.match('---(\w+)---', line)
            if match:
                following_types = match.group(1)
                is_function = following_types == 'functions'
                continue

            try:
                result = _from_line(
                    line, is_function, method_info, layer=layer)

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
        for arg in obj.args:
            arg.cls = obj_by_type.get(arg.type) or (
                [obj_by_name[arg.type]] if arg.type in obj_by_name else []
            )

    yield from obj_all


def find_layer(file_path):
    """Finds the layer used on the specified scheme.tl file."""
    layer_regex = re.compile(r'^//\s*LAYER\s*(\d+)$')
    with open(file_path, 'r', encoding='utf-8') as file:
        for line in file:
            match = layer_regex.match(line)
            if match:
                return int(match.group(1))
