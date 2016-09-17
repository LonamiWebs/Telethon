import re


class TLObject:
    def __init__(self, fullname, id, args, result, is_function):
        """
        Initializes a new TLObject, given its properties.
        Usually, this will be called from `from_tl` instead
        :param fullname: The fullname of the TL object (namespace.name)
                         The namespace can be omitted
        :param id: The hexadecimal string representing the object ID
        :param args: The arguments, if any, of the TL object
        :param result: The result type of the TL object
        :param is_function: Is the object a function or a type?
        """
        # The name can or not have a namespace
        if '.' in fullname:
            self.namespace = fullname.split('.')[0]
            self.name = fullname.split('.')[1]
        else:
            self.namespace = None
            self.name = fullname

        # The ID should be an hexadecimal string
        self.id = int(id, base=16)
        self.args = args
        self.result = result
        self.is_function = is_function

    @staticmethod
    def from_tl(tl, is_function):
        """Returns a TL object from the given TL scheme line"""

        # Regex to match the whole line
        match = re.match(r'''
            ^                  # We want to match from the beginning to the end
            ([\w.]+)           # The .tl object can contain alpha_name or namespace.alpha_name
            \#                 # After the name, comes the ID of the object
            ([0-9a-f]+)        # The constructor ID is in hexadecimal form

            (?:\s              # After that, we want to match its arguments (name:type)
                \{?            # For handling the start of the «{X:Type}» case
                \w+            # The argument name will always be an alpha-only name
                :              # Then comes the separator between name:type
                [\w\d<>#.?!]+  # The type is slightly more complex, since it's alphanumeric and it can
                               # also have Vector<type>, flags:# and flags.0?default, plus :!X as type
                \}?            # For handling the end of the «{X:Type}» case
            )*                 # Match 0 or more arguments
            \s                 # Leave a space between the arguments and the equal
            =
            \s                 # Leave another space between the equal and the result
            ([\w\d<>#.?]+)     # The result can again be as complex as any argument type
            ;$                 # Finally, the line should always end with ;
            ''', tl, re.IGNORECASE | re.VERBOSE)

        # Sub-regex to match the arguments (sadly, it cannot be embedded in the first regex)
        args_match = re.findall(r'''
            (\{)?            # We may or may not capture the opening brace
            (\w+)            # First we capture any alpha name with length 1 or more
            :                # Which is separated from its type by a colon
            ([\w\d<>#.?!]+)  # The type is slightly more complex, since it's alphanumeric and it can
                             # also have Vector<type>, flags:# and flags.0?default, plus :!X as type
            (\})?            # We may or not capture the closing brace
            ''', tl, re.IGNORECASE | re.VERBOSE)

        # Retrieve the matched arguments
        args = [TLArg(name, type, brace != '') for brace, name, type, _ in args_match]

        # And initialize the TLObject
        return TLObject(fullname=match.group(1),
                        id=match.group(2),
                        args=args,
                        result=match.group(3),
                        is_function=is_function)

    def __repr__(self):
        fullname = ('{}.{}'.format(self.namespace, self.name) if self.namespace is not None
                    else self.name)

        hex_id = hex(self.id)[2:].rjust(8, '0')  # Skip 0x and add 0's for padding

        return '{}#{} {} = {}'.format(fullname,
                                      hex_id,
                                      ' '.join([str(arg) for arg in self.args]),
                                      self.result)

    def __str__(self):
        fullname = ('{}.{}'.format(self.namespace, self.name) if self.namespace is not None
                    else self.name)

        # Some arguments are not valid for being represented, such as the flag indicator or generic definition
        # (these have no explicit values until used)
        valid_args = [arg for arg in self.args
                      if not arg.flag_indicator and not arg.generic_definition]

        args = ', '.join(['{}={{}}'.format(arg.name) for arg in valid_args])

        # Since Python's default representation for lists is using repr(), we need to str() manually on every item
        args_format = ', '.join(['str(self.{})'.format(arg.name) if not arg.is_vector else
                                 'None if not self.{0} else [str(_) for _ in self.{0}]'.format(arg.name)
                                 for arg in valid_args])

        return ("'({} (ID: {}) = ({}))'.format({})"
                .format(fullname, hex(self.id), args, args_format))


class TLArg:
    def __init__(self, name, type, generic_definition):
        """
        Initializes a new .tl argument
        :param name: The name of the .tl argument
        :param type: The type of the .tl argument
        :param generic_definition: Is the argument a generic definition?
                                   (i.e. {X:Type})
        """
        if name == 'self':  # This very only name is restricted
            self.name = 'is_self'
        else:
            self.name = name

        # Default values
        self.is_vector = False
        self.is_flag = False
        self.flag_index = -1

        # The type can be an indicator that other arguments will be flags
        if type == '#':
            self.flag_indicator = True
            self.type = None
            self.is_generic = False
        else:
            self.flag_indicator = False
            self.is_generic = type.startswith('!')
            self.type = type.lstrip('!')  # Strip the exclamation mark always to have only the name

            # The type may be a flag (flags.IDX?REAL_TYPE)
            # Note that «flags» is NOT the flags name; this is determined by a previous argument
            # However, we assume that the argument will always be called «flags»
            flag_match = re.match(r'flags.(\d+)\?([\w<>.]+)', self.type)
            if flag_match:
                self.is_flag = True
                self.flag_index = int(flag_match.group(1))
                self.type = flag_match.group(2)  # Update the type to match the exact type, not the "flagged" one

            # Then check if the type is a Vector<REAL_TYPE>
            vector_match = re.match(r'vector<(\w+)>', self.type, re.IGNORECASE)
            if vector_match:
                self.is_vector = True
                self.type = vector_match.group(1)  # Update the type to match the one inside the vector

            # The name may contain "date" in it, if this is the case and the type is "int",
            # we can safely assume that this should be treated as a "date" object.
            # Note that this is not a valid Telegram object, but it's easier to work with
            if re.search(r'(\b|_)date\b', name) and self.type == 'int':
                self.type = 'date'

        self.generic_definition = generic_definition

    def __str__(self):
        # Find the real type representation by updating it as required
        real_type = self.type
        if self.is_vector:
            real_type = 'Vector<{}>'.format(real_type)

        if self.is_generic:
            real_type = '!{}'.format(real_type)

        if self.is_flag:
            real_type = 'flags.{}?{}'.format(self.flag_index, real_type)

        if self.generic_definition:
            return '{{{}:{}}}'.format(self.name, real_type)
        else:
            return '{}:{}'.format(self.name, real_type)
