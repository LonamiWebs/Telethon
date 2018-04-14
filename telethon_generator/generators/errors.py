import itertools


def generate_errors(errors, f):
    # Exact/regex match to create {CODE: ErrorClassName}
    exact_match = []
    regex_match = []

    # Find out what subclasses to import and which to create
    import_base, create_base = set(), {}
    for error in errors:
        if error.subclass_exists:
            import_base.add(error.subclass)
        else:
            create_base[error.subclass] = error.int_code

        if error.has_captures:
            regex_match.append(error)
        else:
            exact_match.append(error)

    # Imports and new subclass creation
    f.write('from .rpc_base_errors import RPCError, {}\n'
            .format(", ".join(sorted(import_base))))

    for cls, int_code in sorted(create_base.items(), key=lambda t: t[1]):
        f.write('\n\nclass {}(RPCError):\n    code = {}\n'
                .format(cls, int_code))

    # Error classes generation
    for error in errors:
        f.write('\n\nclass {}({}):\n    def __init__(self, **kwargs):\n'
                '        '.format(error.name, error.subclass))

        if error.has_captures:
            f.write("self.{} = int(kwargs.get('capture', 0))\n        "
                    .format(error.capture_name))

        f.write('super(Exception, self).__init__({}'
                .format(repr(error.description)))

        if error.has_captures:
            f.write('.format(self.{})'.format(error.capture_name))

        f.write(')\n')

    # Create the actual {CODE: ErrorClassName} dict once classes are defined
    # TODO Actually make a difference between regex/exact
    f.write('\n\nrpc_errors_all = {\n')
    for error in itertools.chain(regex_match, exact_match):
        f.write('    {}: {},\n'.format(repr(error.pattern), error.name))
    f.write('}\n')
