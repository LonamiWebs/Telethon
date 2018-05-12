import re
from zlib import crc32

from ..utils import snake_to_camel_case

CORE_TYPES = (
    0xbc799737,  # boolFalse#bc799737 = Bool;
    0x997275b5,  # boolTrue#997275b5 = Bool;
    0x3fedd339,  # true#3fedd339 = True;
    0x1cb5c415,  # vector#1cb5c415 {t:Type} # [ t ] = Vector t;
)

# https://github.com/telegramdesktop/tdesktop/blob/4bf66cb6e93f3965b40084771b595e93d0b11bcd/Telegram/SourceFiles/codegen/scheme/codegen_scheme.py#L57-L62
WHITELISTED_MISMATCHING_IDS = {
    # 0 represents any layer
    0: {'ipPortSecret', 'accessPointRule', 'help.configSimple'},
    77: {'channel'},
    78: {'channel'}
}


class TLObject:
    def __init__(self, fullname, object_id, args, result, is_function, layer):
        """
        Initializes a new TLObject, given its properties.

        :param fullname: The fullname of the TL object (namespace.name)
                         The namespace can be omitted.
        :param object_id: The hexadecimal string representing the object ID
        :param args: The arguments, if any, of the TL object
        :param result: The result type of the TL object
        :param is_function: Is the object a function or a type?
        :param layer: The layer this TLObject belongs to.
        """
        # The name can or not have a namespace
        self.fullname = fullname
        if '.' in fullname:
            self.namespace, self.name = fullname.split('.', maxsplit=1)
        else:
            self.namespace, self.name = None, fullname

        self.args = args
        self.result = result
        self.is_function = is_function
        self.id = None
        if object_id is None:
            self.id = self.infer_id()
        else:
            self.id = int(object_id, base=16)
            whitelist = WHITELISTED_MISMATCHING_IDS[0] |\
                WHITELISTED_MISMATCHING_IDS.get(layer, set())

            if self.fullname not in whitelist:
                assert self.id == self.infer_id(),\
                    'Invalid inferred ID for ' + repr(self)

        self.class_name = snake_to_camel_case(
            self.name, suffix='Request' if self.is_function else '')

        self.real_args = list(a for a in self.sorted_args() if not
                              (a.flag_indicator or a.generic_definition))

    def sorted_args(self):
        """Returns the arguments properly sorted and ready to plug-in
           into a Python's method header (i.e., flags and those which
           can be inferred will go last so they can default =None)
        """
        return sorted(self.args,
                      key=lambda x: x.is_flag or x.can_be_inferred)

    def __repr__(self, ignore_id=False):
        if self.id is None or ignore_id:
            hex_id = ''
        else:
            hex_id = '#{:08x}'.format(self.id)

        if self.args:
            args = ' ' + ' '.join([repr(arg) for arg in self.args])
        else:
            args = ''

        return '{}{}{} = {}'.format(self.fullname, hex_id, args, self.result)

    def infer_id(self):
        representation = self.__repr__(ignore_id=True)
        representation = representation\
            .replace(':bytes ', ':string ')\
            .replace('?bytes ', '?string ')\
            .replace('<', ' ').replace('>', '')\
            .replace('{', '').replace('}', '')

        representation = re.sub(
            r' \w+:flags\.\d+\?true',
            r'',
            representation
        )
        return crc32(representation.encode('ascii'))


class TLArg:
    def __init__(self, name, arg_type, generic_definition):
        """
        Initializes a new .tl argument
        :param name: The name of the .tl argument
        :param arg_type: The type of the .tl argument
        :param generic_definition: Is the argument a generic definition?
                                   (i.e. {X:Type})
        """
        self.name = 'is_self' if name == 'self' else name

        # Default values
        self.is_vector = False
        self.is_flag = False
        self.skip_constructor_id = False
        self.flag_index = -1

        # Special case: some types can be inferred, which makes it
        # less annoying to type. Currently the only type that can
        # be inferred is if the name is 'random_id', to which a
        # random ID will be assigned if left as None (the default)
        self.can_be_inferred = name == 'random_id'

        # The type can be an indicator that other arguments will be flags
        if arg_type == '#':
            self.flag_indicator = True
            self.type = None
            self.is_generic = False
        else:
            self.flag_indicator = False
            self.is_generic = arg_type.startswith('!')
            # Strip the exclamation mark always to have only the name
            self.type = arg_type.lstrip('!')

            # The type may be a flag (flags.IDX?REAL_TYPE)
            # Note that 'flags' is NOT the flags name; this
            # is determined by a previous argument
            # However, we assume that the argument will always be called 'flags'
            flag_match = re.match(r'flags.(\d+)\?([\w<>.]+)', self.type)
            if flag_match:
                self.is_flag = True
                self.flag_index = int(flag_match.group(1))
                # Update the type to match the exact type, not the "flagged" one
                self.type = flag_match.group(2)

            # Then check if the type is a Vector<REAL_TYPE>
            vector_match = re.match(r'[Vv]ector<([\w\d.]+)>', self.type)
            if vector_match:
                self.is_vector = True

                # If the type's first letter is not uppercase, then
                # it is a constructor and we use (read/write) its ID
                # as pinpointed on issue #81.
                self.use_vector_id = self.type[0] == 'V'

                # Update the type to match the one inside the vector
                self.type = vector_match.group(1)

            # See use_vector_id. An example of such case is ipPort in
            # help.configSpecial
            if self.type.split('.')[-1][0].islower():
                self.skip_constructor_id = True

            # The name may contain "date" in it, if this is the case and the type is "int",
            # we can safely assume that this should be treated as a "date" object.
            # Note that this is not a valid Telegram object, but it's easier to work with
            if self.type == 'int' and (
                        re.search(r'(\b|_)date\b', name) or
                        name in ('expires', 'expires_at', 'was_online')):
                self.type = 'date'

        self.generic_definition = generic_definition

    def type_hint(self):
        type = self.type
        if '.' in type:
            type = type.split('.')[1]
        result = {
            'int': 'int',
            'long': 'int',
            'int128': 'int',
            'int256': 'int',
            'string': 'str',
            'date': 'Optional[datetime]',  # None date = 0 timestamp
            'bytes': 'bytes',
            'true': 'bool',
        }.get(type, "Type{}".format(type))
        if self.is_vector:
            result = 'List[{}]'.format(result)
        if self.is_flag and type != 'date':
            result = 'Optional[{}]'.format(result)

        return result

    def __str__(self):
        # Find the real type representation by updating it as required
        real_type = self.type
        if self.flag_indicator:
            real_type = '#'

        if self.is_vector:
            if self.use_vector_id:
                real_type = 'Vector<{}>'.format(real_type)
            else:
                real_type = 'vector<{}>'.format(real_type)

        if self.is_generic:
            real_type = '!{}'.format(real_type)

        if self.is_flag:
            real_type = 'flags.{}?{}'.format(self.flag_index, real_type)

        if self.generic_definition:
            return '{{{}:{}}}'.format(self.name, real_type)
        else:
            return '{}:{}'.format(self.name, real_type)

    def __repr__(self):
        return str(self).replace(':date', ':int').replace('?date', '?int')


def _from_line(line, is_function, layer):
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
    return TLObject(
        fullname=match.group(1),
        object_id=match.group(2),
        result=match.group(3),
        is_function=is_function,
        layer=layer,
        args=[TLArg(name, arg_type, brace != '')
              for brace, name, arg_type in args_match]
    )


def parse_tl(file_path, layer, ignore_core=False):
    """This method yields TLObjects from a given .tl file."""
    with open(file_path, encoding='utf-8') as file:
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
                result = _from_line(line, is_function, layer=layer)
                if not ignore_core or result.id not in CORE_TYPES:
                    yield result
            except ValueError as e:
                if 'vector#1cb5c415' not in str(e):
                    raise


def find_layer(file_path):
    """Finds the layer used on the specified scheme.tl file."""
    layer_regex = re.compile(r'^//\s*LAYER\s*(\d+)$')
    with open(file_path, encoding='utf-8') as file:
        for line in file:
            match = layer_regex.match(line)
            if match:
                return int(match.group(1))
