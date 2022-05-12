import re
import struct
import zlib

from ...utils import snake_to_camel_case

# https://github.com/telegramdesktop/tdesktop/blob/4bf66cb6e93f3965b40084771b595e93d0b11bcd/Telegram/SourceFiles/codegen/scheme/codegen_scheme.py#L57-L62
WHITELISTED_MISMATCHING_IDS = {
    # 0 represents any layer
    0: {'channel',  # Since layer 77, there seems to be no going back...
        'ipPortSecret', 'accessPointRule', 'help.configSimple'}
}


class TLObject:
    def __init__(self, fullname, object_id, args, result,
                 is_function, usability, friendly, layer):
        """
        Initializes a new TLObject, given its properties.

        :param fullname: The fullname of the TL object (namespace.name)
                         The namespace can be omitted.
        :param object_id: The hexadecimal string representing the object ID
        :param args: The arguments, if any, of the TL object
        :param result: The result type of the TL object
        :param is_function: Is the object a function or a type?
        :param usability: The usability for this method.
        :param friendly: A tuple (namespace, friendly method name) if known.
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
        self.usability = usability
        self.friendly = friendly
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

    @property
    def innermost_result(self):
        index = self.result.find('<')
        if index == -1:
            return self.result
        else:
            return self.result[index + 1:-1]

    def sorted_args(self):
        """Returns the arguments properly sorted and ready to plug-in
           into a Python's method header (i.e., flags and those which
           can be inferred will go last so they can default =None)
        """
        return sorted(self.args,
                      key=lambda x: bool(x.flag) or x.can_be_inferred)

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

        # Remove optional empty values (special-cased to the true type)
        representation = re.sub(
            r' \w+:\w+\.\d+\?true',
            r'',
            representation
        )
        return zlib.crc32(representation.encode('ascii'))

    def to_dict(self):
        return {
            'id':
                str(struct.unpack('i', struct.pack('I', self.id))[0]),
            'method' if self.is_function else 'predicate':
                self.fullname,
            'params':
                [x.to_dict() for x in self.args if not x.generic_definition],
            'type':
                self.result
        }

    def is_good_example(self):
        return not self.class_name.endswith('Empty')

    def as_example(self, f, indent=0):
        f.write('functions' if self.is_function else 'types')
        if self.namespace:
            f.write('.')
            f.write(self.namespace)

        f.write('.')
        f.write(self.class_name)
        f.write('(')

        args = [arg for arg in self.real_args if not arg.omit_example()]
        if not args:
            f.write(')')
            return

        f.write('\n')
        indent += 1
        remaining = len(args)
        for arg in args:
            remaining -= 1
            f.write('    ' * indent)
            f.write(arg.name)
            f.write('=')
            if arg.is_vector:
                f.write('[')
            arg.as_example(f, indent)
            if arg.is_vector:
                f.write(']')
            if remaining:
                f.write(',')
            f.write('\n')

        indent -= 1
        f.write('    ' * indent)
        f.write(')')
