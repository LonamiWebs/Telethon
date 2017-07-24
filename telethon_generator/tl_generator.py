import os
import re
import shutil
from zlib import crc32
from collections import defaultdict

from .parser import SourceBuilder, TLParser


class TLGenerator:
    def __init__(self, output_dir):
        self.output_dir = output_dir

    def _get_file(self, *paths):
        return os.path.join(self.output_dir, *paths)

    def _rm_if_exists(self, filename):
        file = self._get_file(filename)
        if os.path.exists(file):
            if os.path.isdir(file):
                shutil.rmtree(file)
            else:
                os.remove(file)

    def tlobjects_exist(self):
        """Determines whether the TLObjects were previously
           generated (hence exist) or not
        """
        return os.path.isfile(self._get_file('all_tlobjects.py'))

    def clean_tlobjects(self):
        """Cleans the automatically generated TLObjects from disk"""
        for name in ('functions', 'types', 'all_tlobjects.py'):
            self._rm_if_exists(name)

    def generate_tlobjects(self, scheme_file, import_depth):
        """Generates all the TLObjects from scheme.tl to
           tl/functions and tl/types
        """

        # First ensure that the required parent directories exist
        os.makedirs(self._get_file('functions'), exist_ok=True)
        os.makedirs(self._get_file('types'), exist_ok=True)

        # Step 0: Cache the parsed file on a tuple
        tlobjects = tuple(TLParser.parse_file(scheme_file))

        # Step 1: Ensure that no object has the same name as a namespace
        # We must check this because Python will complain if it sees a
        # file and a directory with the same name, which happens for
        # example with "updates".
        #
        # We distinguish between function and type namespaces since we
        # will later need to perform a relative import for them to be used
        function_namespaces = set()
        type_namespaces = set()

        # Make use of this iteration to also store 'Type: [Constructors]'
        type_constructors = defaultdict(list)
        for tlobject in tlobjects:
            if tlobject.is_function:
                if tlobject.namespace:
                    function_namespaces.add(tlobject.namespace)
            else:
                type_constructors[tlobject.result].append(tlobject)
                if tlobject.namespace:
                    type_namespaces.add(tlobject.namespace)

        # Merge both namespaces to easily check if any namespace exists,
        # though we could also distinguish between types and functions
        # here, it's not worth doing
        namespace_directories = function_namespaces | type_namespaces
        for tlobject in tlobjects:
            if TLGenerator.get_file_name(tlobject, add_extension=False) \
                    in namespace_directories:
                # If this TLObject isn't under the same directory as its
                # name (i.e. "contacts"), append "_tg" to avoid confusion
                # between the file and the directory (i.e. "updates")
                if tlobject.namespace != tlobject.name:
                    tlobject.name += '_tg'

        # Step 2: Generate the actual code
        for tlobject in tlobjects:
            # Omit core types, these are embedded in the generated code
            if tlobject.is_core_type():
                continue

            # Determine the output directory and create it
            out_dir = self._get_file('functions'
                                     if tlobject.is_function else 'types')

            # Path depth to perform relative import
            depth = import_depth
            if tlobject.namespace:
                depth += 1
                out_dir = os.path.join(out_dir, tlobject.namespace)

            os.makedirs(out_dir, exist_ok=True)

            # Add this object to __init__.py, so we can import *
            init_py = os.path.join(out_dir, '__init__.py')
            with open(init_py, 'a', encoding='utf-8') as file:
                with SourceBuilder(file) as builder:
                    builder.writeln('from .{} import {}'.format(
                        TLGenerator.get_file_name(tlobject, add_extension=False),
                        TLGenerator.get_class_name(tlobject)))

            # Create the file for this TLObject
            filename = os.path.join(out_dir, TLGenerator.get_file_name(
                tlobject, add_extension=True
            ))

            with open(filename, 'w', encoding='utf-8') as file:
                with SourceBuilder(file) as builder:
                    TLGenerator._write_source_code(
                        tlobject, builder, depth, type_constructors)

        # Step 3: Add the relative imports to the namespaces on __init__.py's
        init_py = self._get_file('functions', '__init__.py')
        with open(init_py, 'a') as file:
            file.write('from . import {}\n'
                       .format(', '.join(function_namespaces)))

        init_py = self._get_file('types', '__init__.py')
        with open(init_py, 'a') as file:
            file.write('from . import {}\n'
                       .format(', '.join(type_namespaces)))

        # Step 4: Once all the objects have been generated,
        #         we can now group them in a single file
        filename = os.path.join(self._get_file('all_tlobjects.py'))
        with open(filename, 'w', encoding='utf-8') as file:
            with SourceBuilder(file) as builder:
                builder.writeln(
                    '"""File generated by TLObjects\' generator. All changes will be ERASED"""')
                builder.writeln()

                builder.writeln('from . import types, functions')
                builder.writeln()

                # Create a variable to indicate which layer this is
                builder.writeln('layer = {}  # Current generated layer'.format(
                    TLParser.find_layer(scheme_file)))
                builder.writeln()

                # Then create the dictionary containing constructor_id: class
                builder.writeln('tlobjects = {')
                builder.current_indent += 1

                # Fill the dictionary (0x1a2b3c4f: tl.full.type.path.Class)
                for tlobject in tlobjects:
                    constructor = hex(tlobject.id)
                    if len(constructor) != 10:
                        # Make it a nice length 10 so it fits well
                        constructor = '0x' + constructor[2:].zfill(8)

                    builder.write('{}: '.format(constructor))
                    builder.write(
                        'functions' if tlobject.is_function else 'types')

                    if tlobject.namespace:
                        builder.write('.' + tlobject.namespace)

                    builder.writeln('.{},'.format(
                        TLGenerator.get_class_name(tlobject)))

                builder.current_indent -= 1
                builder.writeln('}')

    @staticmethod
    def _write_source_code(tlobject, builder, depth, type_constructors):
        """Writes the source code corresponding to the given TLObject
           by making use of the 'builder' SourceBuilder.

           Additional information such as file path depth and
           the Type: [Constructors] must be given for proper
           importing and documentation strings.
        '"""

        # Both types and functions inherit from the TLObject class so they
        # all can be serialized and sent, however, only the functions are
        # "content_related".
        builder.writeln('from {}.tl.tlobject import TLObject'
                        .format('.' * depth))

        if tlobject.is_function:
            util_imports = set()
            for a in tlobject.args:
                # We can automatically convert some "full" types to
                # "input only" (like User -> InputPeerUser, etc.)
                if a.type == 'InputPeer':
                    util_imports.add('get_input_peer')
                elif a.type == 'InputChannel':
                    util_imports.add('get_input_channel')
                elif a.type == 'InputUser':
                    util_imports.add('get_input_user')

            if util_imports:
                builder.writeln('from {}.utils import {}'.format(
                    '.' * depth, ', '.join(util_imports)))

        if any(a for a in tlobject.args if a.can_be_inferred):
            # Currently only 'random_id' needs 'os' to be imported
            builder.writeln('import os')

        builder.writeln()
        builder.writeln()
        builder.writeln('class {}(TLObject):'.format(
            TLGenerator.get_class_name(tlobject)))

        # Write the original .tl definition,
        # along with a "generated automatically" message
        builder.writeln(
            '"""Class generated by TLObjects\' generator. '
            'All changes will be ERASED. TL definition below.'
        )
        builder.writeln('{}"""'.format(repr(tlobject)))
        builder.writeln()

        # Class-level variable to store its constructor ID
        builder.writeln("# Telegram's constructor (U)ID for this class")
        builder.writeln('constructor_id = {}'.format(hex(tlobject.id)))
        builder.writeln("# Also the ID of its resulting type for fast checks")
        builder.writeln('subclass_of_id = {}'.format(
            hex(crc32(tlobject.result.encode('ascii')))))
        builder.writeln()

        # Flag arguments must go last
        args = [
            a for a in tlobject.sorted_args()
            if not a.flag_indicator and not a.generic_definition
        ]

        # Convert the args to string parameters, flags having =None
        args = [
            (a.name if not a.is_flag and not a.can_be_inferred
             else '{}=None'.format(a.name))
            for a in args
        ]

        # Write the __init__ function
        if args:
            builder.writeln(
                'def __init__(self, {}):'.format(', '.join(args))
            )
        else:
            builder.writeln('def __init__(self):')

        # Now update args to have the TLObject arguments, _except_
        # those which are calculated on send or ignored, this is
        # flag indicator and generic definitions.
        #
        # We don't need the generic definitions in Python
        # because arguments can be any type
        args = [arg for arg in tlobject.args
                if not arg.flag_indicator and
                not arg.generic_definition]

        if args:
            # Write the docstring, to know the type of the args
            builder.writeln('"""')
            for arg in args:
                if not arg.flag_indicator:
                    builder.write(
                        ':param {}: Telegram type: "{}".'
                        .format(arg.name, arg.type)
                    )
                    if arg.is_vector:
                        builder.write(' Must be a list.'.format(arg.name))

                    if arg.is_generic:
                        builder.write(' Must be another TLObject request.')

                    builder.writeln()

            # We also want to know what type this request returns
            # or to which type this constructor belongs to
            builder.writeln()
            if tlobject.is_function:
                builder.write(':returns {}: '.format(tlobject.result))
            else:
                builder.write('Constructor for {}: '.format(tlobject.result))

            constructors = type_constructors[tlobject.result]
            if not constructors:
                builder.writeln('This type has no constructors.')
            elif len(constructors) == 1:
                builder.writeln('Instance of {}.'.format(
                    TLGenerator.get_class_name(constructors[0])
                ))
            else:
                builder.writeln('Instance of either {}.'.format(
                    ', '.join(TLGenerator.get_class_name(c)
                              for c in constructors)
                ))

            builder.writeln('"""')

        builder.writeln('super().__init__()')
        # Functions have a result object and are confirmed by default
        if tlobject.is_function:
            builder.writeln('self.result = None')
            builder.writeln(
                'self.content_related = True')

        # Set the arguments
        if args:
            # Leave an empty line if there are any args
            builder.writeln()

        for arg in args:
            if arg.can_be_inferred:
                # Currently the only argument that can be
                # inferred are those called 'random_id'
                if arg.name == 'random_id':
                    builder.writeln(
                        "self.random_id = random_id if random_id "
                        "is not None else int.from_bytes("
                        "os.urandom({}), signed=True, "
                        "byteorder='little')"
                        .format(8 if arg.type == 'long' else 4)
                    )
                else:
                    raise ValueError('Cannot infer a value for ', arg)

            # Well-known cases, auto-cast it to the right type
            elif arg.type == 'InputPeer' and tlobject.is_function:
                TLGenerator.write_get_input(builder, arg, 'get_input_peer')
            elif arg.type == 'InputChannel' and tlobject.is_function:
                TLGenerator.write_get_input(builder, arg, 'get_input_channel')
            elif arg.type == 'InputUser' and tlobject.is_function:
                TLGenerator.write_get_input(builder, arg, 'get_input_user')

            else:
                builder.writeln('self.{0} = {0}'.format(arg.name))

        builder.end_block()

        # Write the to_dict(self) method
        if args:
            builder.writeln('def to_dict(self):')
            builder.writeln('return {')
            builder.current_indent += 1

            base_types = ('string', 'bytes', 'int', 'long', 'int128',
                          'int256', 'double', 'Bool', 'true', 'date')

            for arg in args:
                builder.write("'{}': ".format(arg.name))
                if arg.type in base_types:
                    if arg.is_vector:
                        builder.write(
                            '[] if self.{0} is None else self.{0}[:]'
                            .format(arg.name)
                        )
                    else:
                        builder.write('self.{}'.format(arg.name))
                else:
                    if arg.is_vector:
                        builder.write(
                            '[] if self.{0} is None else [None '
                            'if x is None else x.to_dict() for x in self.{0}]'
                            .format(arg.name)
                        )
                    else:
                        builder.write(
                            'None if self.{0} is None else self.{0}.to_dict()'
                            .format(arg.name)
                        )
                builder.writeln(',')

            builder.current_indent -= 1
            builder.writeln("}")
        else:
            builder.writeln('@staticmethod')
            builder.writeln('def to_dict():')
            builder.writeln('return {}')

        builder.end_block()

        # Write the on_send(self, writer) function
        builder.writeln('def on_send(self, writer):')
        builder.writeln(
            'writer.write_int({}.constructor_id, signed=False)'
                .format(TLGenerator.get_class_name(tlobject)))

        for arg in tlobject.args:
            TLGenerator.write_onsend_code(builder, arg,
                                          tlobject.args)
        builder.end_block()

        # Write the empty() function, which returns an "empty"
        # instance, in which all attributes are set to None
        builder.writeln('@staticmethod')
        builder.writeln('def empty():')
        builder.writeln(
            '"""Returns an "empty" instance (attributes=None)"""')
        builder.writeln('return {}({})'.format(
            TLGenerator.get_class_name(tlobject), ', '.join(
                'None' for _ in range(len(args)))))
        builder.end_block()

        # Write the on_response(self, reader) function
        builder.writeln('def on_response(self, reader):')
        # Do not read constructor's ID, since
        # that's already been read somewhere else
        if tlobject.is_function:
            TLGenerator.write_request_result_code(builder, tlobject)
        else:
            if tlobject.args:
                for arg in tlobject.args:
                    TLGenerator.write_onresponse_code(
                        builder, arg, tlobject.args)
            else:
                # If there were no arguments, we still need an
                # on_response method, and hence "pass" if empty
                builder.writeln('pass')
        builder.end_block()

        # Write the __repr__(self) and __str__(self) functions
        builder.writeln('def __repr__(self):')
        builder.writeln("return '{}'".format(repr(tlobject)))
        builder.end_block()

        builder.writeln('def __str__(self):')
        builder.writeln('return TLObject.pretty_format(self)')
        builder.end_block()

        builder.writeln('def stringify(self):')
        builder.writeln('return TLObject.pretty_format(self, indent=0)')
        # builder.end_block()  # No need to end the last block

    @staticmethod
    def write_get_input(builder, arg, get_input_code):
        """Returns "True" if the get_input_* code was written when assigning
           a parameter upon creating the request. Returns False otherwise
        """
        if arg.is_vector:
            builder.writeln(
                'self.{0} = [{1}(_x) for _x in {0}]'
                .format(arg.name, get_input_code)
            )
            pass
        else:
            builder.writeln(
                'self.{0} = {1}({0})'.format(arg.name, get_input_code)
            )

    @staticmethod
    def get_class_name(tlobject):
        """Gets the class name following the Python style guidelines, in ThisClassFormat"""

        # Courtesy of http://stackoverflow.com/a/31531797/4759433
        # Also, '_' could be replaced for ' ', then use .title(), and then remove ' '
        result = re.sub(r'_([a-z])', lambda m: m.group(1).upper(),
                        tlobject.name)
        result = result[:1].upper() + result[1:].replace(
            '_', '')  # Replace again to fully ensure!
        # If it's a function, let it end with "Request" to identify them more easily
        if tlobject.is_function:
            result += 'Request'
        return result

    @staticmethod
    def get_file_name(tlobject, add_extension=False):
        """Gets the file name in file_name_format.py for the given TLObject"""

        # Courtesy of http://stackoverflow.com/a/1176023/4759433
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', tlobject.name)
        result = re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
        if add_extension:
            return result + '.py'
        else:
            return result

    @staticmethod
    def write_onsend_code(builder, arg, args, name=None):
        """
        Writes the write code for the given argument
        :param builder: The source code builder
        :param arg: The argument to write
        :param args: All the other arguments in TLObject same on_send. This is required to determine the flags value
        :param name: The name of the argument. Defaults to "self.argname"
                     This argument is an option because it's required when writing Vectors<>
        """

        if arg.generic_definition:
            return  # Do nothing, this only specifies a later type

        if name is None:
            name = 'self.{}'.format(arg.name)

        # The argument may be a flag, only write if it's not None AND if it's not a True type
        # True types are not actually sent, but instead only used to determine the flags
        if arg.is_flag:
            if arg.type == 'true':
                return  # Exit, since True type is never written
            else:
                builder.writeln('if {}:'.format(name))

        if arg.is_vector:
            if arg.use_vector_id:
                builder.writeln(
                    "writer.write_int(0x1cb5c415, signed=False)  # Vector's constructor ID")

            builder.writeln('writer.write_int(len({}))'.format(name))
            builder.writeln('for _x in {}:'.format(name))
            # Temporary disable .is_vector, not to enter this if again
            arg.is_vector = False
            TLGenerator.write_onsend_code(builder, arg, args, name='_x')
            arg.is_vector = True

        elif arg.flag_indicator:
            # Calculate the flags with those items which are not None
            builder.writeln(
                '# Calculate the flags. This equals to those flag arguments which are NOT None')
            builder.writeln('flags = 0')
            for flag in args:
                if flag.is_flag:
                    builder.writeln('flags |= (1 << {}) if {} else 0'.format(
                        flag.flag_index, 'self.{}'.format(flag.name)))

            builder.writeln('writer.write_int(flags)')
            builder.writeln()

        elif 'int' == arg.type:
            builder.writeln('writer.write_int({})'.format(name))

        elif 'long' == arg.type:
            builder.writeln('writer.write_long({})'.format(name))

        elif 'int128' == arg.type:
            builder.writeln('writer.write_large_int({}, bits=128)'.format(
                name))

        elif 'int256' == arg.type:
            builder.writeln('writer.write_large_int({}, bits=256)'.format(
                name))

        elif 'double' == arg.type:
            builder.writeln('writer.write_double({})'.format(name))

        elif 'string' == arg.type:
            builder.writeln('writer.tgwrite_string({})'.format(name))

        elif 'Bool' == arg.type:
            builder.writeln('writer.tgwrite_bool({})'.format(name))

        elif 'true' == arg.type:  # Awkwardly enough, Telegram has both bool and "true", used in flags
            pass  # These are actually NOT written! Only used for flags

        elif 'bytes' == arg.type:
            builder.writeln('writer.tgwrite_bytes({})'.format(name))

        elif 'date' == arg.type:  # Custom format
            builder.writeln('writer.tgwrite_date({})'.format(name))

        else:
            # Else it may be a custom type
            builder.writeln('{}.on_send(writer)'.format(name))

        # End vector and flag blocks if required (if we opened them before)
        if arg.is_vector:
            builder.end_block()

        if arg.is_flag:
            builder.end_block()

    @staticmethod
    def write_onresponse_code(builder, arg, args, name=None):
        """
        Writes the receive code for the given argument

        :param builder: The source code builder
        :param arg: The argument to write
        :param args: All the other arguments in TLObject same on_send. This is required to determine the flags value
        :param name: The name of the argument. Defaults to "self.argname"
                     This argument is an option because it's required when writing Vectors<>
        """

        if arg.generic_definition:
            return  # Do nothing, this only specifies a later type

        if name is None:
            name = 'self.{}'.format(arg.name)

        # The argument may be a flag, only write that flag was given!
        was_flag = False
        if arg.is_flag:
            was_flag = True
            builder.writeln('if (flags & (1 << {})) != 0:'.format(
                arg.flag_index))
            # Temporary disable .is_flag not to enter this if again when calling the method recursively
            arg.is_flag = False

        if arg.is_vector:
            if arg.use_vector_id:
                builder.writeln("reader.read_int()  # Vector's constructor ID")

            builder.writeln('{} = []  # Initialize an empty list'.format(name))
            builder.writeln('_len = reader.read_int()')
            builder.writeln('for _ in range(_len):')
            # Temporary disable .is_vector, not to enter this if again
            arg.is_vector = False
            TLGenerator.write_onresponse_code(builder, arg, args, name='_x')
            builder.writeln('{}.append(_x)'.format(name))
            arg.is_vector = True

        elif arg.flag_indicator:
            # Read the flags, which will indicate what items we should read next
            builder.writeln('flags = reader.read_int()')
            builder.writeln()

        elif 'int' == arg.type:
            builder.writeln('{} = reader.read_int()'.format(name))

        elif 'long' == arg.type:
            builder.writeln('{} = reader.read_long()'.format(name))

        elif 'int128' == arg.type:
            builder.writeln(
                '{} = reader.read_large_int(bits=128)'.format(name)
            )

        elif 'int256' == arg.type:
            builder.writeln(
                '{} = reader.read_large_int(bits=256)'.format(name)
            )

        elif 'double' == arg.type:
            builder.writeln('{} = reader.read_double()'.format(name))

        elif 'string' == arg.type:
            builder.writeln('{} = reader.tgread_string()'.format(name))

        elif 'Bool' == arg.type:
            builder.writeln('{} = reader.tgread_bool()'.format(name))

        elif 'true' == arg.type:  # Awkwardly enough, Telegram has both bool and "true", used in flags
            builder.writeln(
                '{} = True  # Arbitrary not-None value, no need to read since it is a flag'.
                format(name))

        elif 'bytes' == arg.type:
            builder.writeln('{} = reader.tgread_bytes()'.format(name))

        elif 'date' == arg.type:  # Custom format
            builder.writeln('{} = reader.tgread_date()'.format(name))

        else:
            # Else it may be a custom type
            builder.writeln('{} = reader.tgread_object()'.format(name))

        # End vector and flag blocks if required (if we opened them before)
        if arg.is_vector:
            builder.end_block()

        if was_flag:
            builder.end_block()
            # Restore .is_flag
            arg.is_flag = True

    @staticmethod
    def write_request_result_code(builder, tlobject):
        """
        Writes the receive code for the given function

        :param builder: The source code builder
        :param tlobject: The TLObject for which the 'self.result = ' will be written
        """
        if tlobject.result.startswith('Vector<'):
            # Vector results are a bit special since they can also be composed
            # of integer values and such; however, the result of requests is
            # not parsed as arguments are and it's a bit harder to tell which
            # is which.
            if tlobject.result == 'Vector<int>':
                builder.writeln('reader.read_int()  # Vector id')
                builder.writeln('count = reader.read_int()')
                builder.writeln('self.result = [reader.read_int() for _ in range(count)]')

            elif tlobject.result == 'Vector<long>':
                builder.writeln('reader.read_int()  # Vector id')
                builder.writeln('count = reader.read_long()')
                builder.writeln('self.result = [reader.read_long() for _ in range(count)]')

            else:
                builder.writeln('self.result = reader.tgread_vector()')
        else:
            builder.writeln('self.result = reader.tgread_object()')
