import re


def _fmt_strings(*dicts):
    for d in dicts:
        for k, v in d.items():
            if v in ('None', 'True', 'False'):
                d[k] = '<strong>{}</strong>'.format(v)
            else:
                d[k] = re.sub(
                    r'([brf]?([\'"]).*\2)',
                    lambda m: '<em>{}</em>'.format(m.group(1)),
                    v
                )


KNOWN_NAMED_EXAMPLES = {
    ('message', 'string'): "'Hello there!'",
    ('expires_at', 'date'): 'datetime.timedelta(minutes=5)',
    ('until_date', 'date'): 'datetime.timedelta(days=14)',
    ('view_messages', 'true'): 'None',
    ('send_messages', 'true'): 'None',
    ('limit', 'int'): '100',
    ('hash', 'int'): '0',
    ('hash', 'string'): "'A4LmkR23G0IGxBE71zZfo1'",
    ('min_id', 'int'): '0',
    ('max_id', 'int'): '0',
    ('min_id', 'long'): '0',
    ('max_id', 'long'): '0',
    ('add_offset', 'int'): '0',
    ('title', 'string'): "'My awesome title'",
    ('device_model', 'string'): "'ASUS Laptop'",
    ('system_version', 'string'): "'Arch Linux'",
    ('app_version', 'string'): "'1.0'",
    ('system_lang_code', 'string'): "'en'",
    ('lang_pack', 'string'): "''",
    ('lang_code', 'string'): "'en'",
    ('chat_id', 'int'): '478614198',
    ('client_id', 'long'): 'random.randrange(-2**63, 2**63)',
    ('video', 'InputFile'): "client.upload_file('/path/to/file.mp4')",
}

KNOWN_TYPED_EXAMPLES = {
    'int128': "int.from_bytes(os.urandom(16), 'big')",
    'bytes': "b'arbitrary\\x7f data \\xfa here'",
    'long': "-12398745604826",
    'string': "'some string here'",
    'int': '42',
    'date': 'datetime.datetime(2018, 6, 25)',
    'double': '7.13',
    'Bool': 'False',
    'true': 'True',
    'InputChatPhoto': "client.upload_file('/path/to/photo.jpg')",
    'InputFile': "client.upload_file('/path/to/file.jpg')",
    'InputPeer': "'username'"
}

_fmt_strings(KNOWN_NAMED_EXAMPLES, KNOWN_TYPED_EXAMPLES)

SYNONYMS = {
    'InputUser': 'InputPeer',
    'InputChannel': 'InputPeer',
    'InputDialogPeer': 'InputPeer',
    'InputNotifyPeer': 'InputPeer',
    'InputMessage': 'int'
}

# These are flags that are cleaner to leave off
OMITTED_EXAMPLES = {
    'silent',
    'background',
    'clear_draft',
    'reply_to_msg_id',
    'random_id',
    'reply_markup',
    'entities',
    'embed_links',
    'hash',
    'min_id',
    'max_id',
    'add_offset',
    'grouped',
    'broadcast',
    'admins',
    'edit',
    'delete'
}


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
        self.flag = None  # name of the flag to check if self is present
        self.skip_constructor_id = False
        self.flag_index = -1  # bit index of the flag to check if self is present
        self.cls = None

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

            # The type may be a flag (FLAGS.IDX?REAL_TYPE)
            # FLAGS can be any name, but it should have appeared previously.
            flag_match = re.match(r'(\w+).(\d+)\?([\w<>.]+)', self.type)
            if flag_match:
                self.flag = flag_match.group(1)
                self.flag_index = int(flag_match.group(2))
                # Update the type to match the exact type, not the "flagged" one
                self.type = flag_match.group(3)

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

            # The name may contain "date" in it, if this is the case and
            # the type is "int", we can safely assume that this should be
            # treated as a "date" object. Note that this is not a valid
            # Telegram object, but it's easier to work with
            if self.type == 'int' and (
                        re.search(r'(\b|_)(date|until|since)(\b|_)', name) or
                        name in ('expires', 'expires_at', 'was_online')):
                self.type = 'date'

        self.generic_definition = generic_definition

    def type_hint(self):
        cls = self.type
        if '.' in cls:
            cls = cls.split('.')[1]
        result = {
            'int': 'int',
            'long': 'int',
            'int128': 'int',
            'int256': 'int',
            'double': 'float',
            'string': 'str',
            'date': 'Optional[datetime]',  # None date = 0 timestamp
            'bytes': 'bytes',
            'Bool': 'bool',
            'true': 'bool',
        }.get(cls, "'Type{}'".format(cls))
        if self.is_vector:
            result = 'List[{}]'.format(result)
        if self.flag and cls != 'date':
            result = 'Optional[{}]'.format(result)

        return result

    def real_type(self):
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

        if self.flag:
            real_type = '{}.{}?{}'.format(self.flag, self.flag_index, real_type)

        return real_type

    def __str__(self):
        if self.generic_definition:
            return '{{{}:{}}}'.format(self.name, self.real_type())
        else:
            return '{}:{}'.format(self.name, self.real_type())

    def __repr__(self):
        return str(self).replace(':date', ':int').replace('?date', '?int')

    def to_dict(self):
        return {
            'name': self.name.replace('is_self', 'self'),
            'type': re.sub(r'\bdate$', 'int', self.real_type())
        }

    def as_example(self, f, indent=0):
        if self.is_generic:
            f.write('other_request')
            return

        known = (KNOWN_NAMED_EXAMPLES.get((self.name, self.type))
                 or KNOWN_TYPED_EXAMPLES.get(self.type)
                 or KNOWN_TYPED_EXAMPLES.get(SYNONYMS.get(self.type)))
        if known:
            f.write(known)
            return

        assert self.omit_example() or self.cls, 'TODO handle ' + str(self)

        # Pick an interesting example if any
        for cls in self.cls:
            if cls.is_good_example():
                cls.as_example(f, indent)
                break
        else:
            # If no example is good, just pick the first
            self.cls[0].as_example(f, indent)

    def omit_example(self):
        return (self.flag or self.can_be_inferred) \
               and self.name in OMITTED_EXAMPLES
