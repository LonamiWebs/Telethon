import re


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

            # The name may contain "date" in it, if this is the case and
            # the type is "int", we can safely assume that this should be
            # treated as a "date" object. Note that this is not a valid
            # Telegram object, but it's easier to work with
            if self.type == 'int' and (
                        re.search(r'(\b|_)date\b', name) or
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
            'string': 'str',
            'date': 'Optional[datetime]',  # None date = 0 timestamp
            'bytes': 'bytes',
            'true': 'bool',
        }.get(cls, "Type{}".format(cls))
        if self.is_vector:
            result = 'List[{}]'.format(result)
        if self.is_flag and cls != 'date':
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

        if self.is_flag:
            real_type = 'flags.{}?{}'.format(self.flag_index, real_type)

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
